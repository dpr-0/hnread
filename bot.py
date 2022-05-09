import argparse
import logging
from datetime import timedelta
from enum import IntEnum, auto
from functools import partial
from typing import List, Type, Union

from decouple import config
from telegram import Bot, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Updater,
)

from hnread import items, repos, services
from hnread.topics import Topic

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


class BaseStoriesEventHandler(services.EventHandler):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    def get_display_class(self) -> Type[items.StoryDisplay]:
        pass

    def handle(
        self,
        subscribers: List[repos.Subscriber],
        item: Union[items.Story, items.Job, items.Poll],
    ):
        display_text = str(self.get_display_class()(item))
        for subscriber in subscribers:
            self.bot.send_message(subscriber.id, display_text, parse_mode="HTML")


class TopStoriesEventHandler(BaseStoriesEventHandler):
    def get_display_class(self) -> Type[items.TopStoryDisplay]:
        return items.TopStoryDisplay


class BestStoriesEventHandler(BaseStoriesEventHandler):
    def get_display_class(self) -> Type[items.BestStoryDisplay]:
        return items.BestStoryDisplay


def help_command(update: Update, context: CallbackContext) -> None:
    if (message := update.message) is not None:
        message.reply_text("help")


def ping_command(update: Update, context: CallbackContext) -> None:
    if (message := update.message) is not None:
        message.reply_text("Pong!")


class SubscribeState(IntEnum):
    FIRST = auto()


class UnSubscribeState(IntEnum):
    FIRST = auto()


def list_topic(
    update: Update, context: CallbackContext, services: services.HNSubscribeService
) -> int:
    inline_keyboard_bottons = [
        InlineKeyboardButton(text, callback_data=f"{enum}")
        for enum, text, in services.list_topic().items()
    ]
    keyboard = [inline_keyboard_bottons]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Subscribe a topic from the list below:", reply_markup=reply_markup
    )
    return SubscribeState.FIRST


def list_subscribed_topic(
    update: Update, context: CallbackContext, services: services.HNSubscribeService
):

    inline_keyboard_bottons = [
        InlineKeyboardButton(text, callback_data=f"{enum}")
        for enum, text in services.list_subscribed_topic(update.message.chat_id).items()
    ]
    keyboard = [inline_keyboard_bottons]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Here is your subscribed topics, you can click botton to unsubscribe topic.",
        reply_markup=reply_markup,
    )
    return UnSubscribeState.FIRST


def subscribe(
    update: Update,
    context: CallbackContext,
    services: services.HNSubscribeService,
    topic: Topic,
) -> int:

    query = update.callback_query
    query.answer()
    services.subscribe(topic, repos.Subscriber(id=query.message.chat_id))
    topic_display = services.list_topic()[topic]
    query.edit_message_text(f"Subscribed Topic: {topic_display} !")
    return ConversationHandler.END


def unsubscribe(
    update: Update,
    context: CallbackContext,
    services: services.HNSubscribeService,
    topic: Topic,
) -> int:

    query = update.callback_query
    query.answer()
    services.unsubscribe(topic, repos.Subscriber(id=query.message.chat_id))
    topic_display = services.list_topic()[topic]
    query.edit_message_text(f"Unsubscribed Topic:{topic_display} !")
    return ConversationHandler.END


def publish_topstories(context: CallbackContext, services: services.NHPublishService):
    services.publish_stories(Topic.top)


def publish_beststories(context: CallbackContext, services: services.NHPublishService):
    services.publish_stories(Topic.best)


def main() -> None:
    BOT_TOKEN = config("BOT_TOKEN")
    REDIS_URL = config("REDIS_URL")
    sub_service = services.HNSubscribeService(repos.RedisPubSubRepository(REDIS_URL))
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--reset_db",
        default=lambda: repos.RedisPubSubRepository(REDIS_URL).flush(),
        help="reset db",
        action="store_true",
    )
    parser.parse_args()
    """Start the bot."""
    # Create the Updater and pass it your bot's token.

    updater = Updater(BOT_TOKEN)
    bot = updater.bot

    updater.bot.set_my_commands(
        [
            # BotCommand("help", "help"),
            BotCommand("ping", "ping"),
            BotCommand("subscribe", "subscribe topics"),
            BotCommand("list_subscribed", "list subscribed topics"),
        ]
    )
    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("ping", ping_command))
    dispatcher.add_handler(
        ConversationHandler(
            entry_points=[
                CommandHandler("subscribe", partial(list_topic, services=sub_service))
            ],
            states={
                SubscribeState.FIRST: [
                    CallbackQueryHandler(
                        partial(subscribe, services=sub_service, topic=Topic.top),
                        pattern=f"^{Topic.top}$",
                    ),
                    CallbackQueryHandler(
                        partial(subscribe, services=sub_service, topic=Topic.best),
                        pattern=f"^{Topic.best}$",
                    ),
                ]
            },
            fallbacks=[
                CommandHandler("subscribe", partial(list_topic, services=sub_service))
            ],
        )
    )
    dispatcher.add_handler(
        ConversationHandler(
            entry_points=[
                CommandHandler(
                    "list_subscribed",
                    partial(list_subscribed_topic, services=sub_service),
                )
            ],
            states={
                UnSubscribeState.FIRST: [
                    CallbackQueryHandler(
                        partial(unsubscribe, services=sub_service, topic=Topic.top),
                        pattern=f"^{Topic.top}$",
                    ),
                    CallbackQueryHandler(
                        partial(unsubscribe, services=sub_service, topic=Topic.best),
                        pattern=f"^{Topic.best}$",
                    ),
                ]
            },
            fallbacks=[
                CommandHandler(
                    "list_subscribed",
                    partial(list_subscribed_topic, services=sub_service),
                )
            ],
        )
    )

    pub_service = (
        services.NHPublishService(
            hn_repo=repos.HNRepository(),
            pubsub_repo=repos.RedisPubSubRepository(REDIS_URL),
        )
        .add_handler(Topic.top, TopStoriesEventHandler(bot))
        .add_handler(Topic.best, BestStoriesEventHandler(bot))
    )

    job_queue = updater.job_queue
    job_queue.run_repeating(
        partial(publish_topstories, services=pub_service),
        interval=timedelta(seconds=30),
        name="publish_topstories",
    )
    job_queue.run_repeating(
        partial(publish_beststories, services=pub_service),
        interval=timedelta(seconds=300),
        name="publish_beststories",
    )
    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == "__main__":
    main()
