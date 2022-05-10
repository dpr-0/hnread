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

BOT_TOKEN = config("BOT_TOKEN")
REDIS_URL = config("REDIS_URL")


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


def list_topic(update: Update, context: CallbackContext) -> int:
    sub_service = services.HNSubscribeService(repos.RedisPubSubRepository(REDIS_URL))
    inline_keyboard_bottons = [
        InlineKeyboardButton(text, callback_data=f"{enum}")
        for enum, text, in sub_service.list_topic().items()
    ]
    keyboard = [inline_keyboard_bottons]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Subscribe a topic from the list below:", reply_markup=reply_markup
    )
    return SubscribeState.FIRST


def list_subscribed_topic(update: Update, context: CallbackContext):
    sub_service = services.HNSubscribeService(repos.RedisPubSubRepository(REDIS_URL))
    inline_keyboard_bottons = [
        InlineKeyboardButton(text, callback_data=f"{enum}")
        for enum, text in sub_service.list_subscribed_topic(
            update.message.chat_id
        ).items()
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
    topic: Topic,
) -> int:
    query = update.callback_query
    query.answer()

    sub_service = services.HNSubscribeService(repos.RedisPubSubRepository(REDIS_URL))
    sub_service.subscribe(topic, repos.Subscriber(id=query.message.chat_id))

    query.edit_message_text(f"Subscribed {sub_service.list_topic()[topic]} !")
    return ConversationHandler.END


def unsubscribe(
    update: Update,
    context: CallbackContext,
    topic: Topic,
) -> int:
    query = update.callback_query
    query.answer()

    sub_service = services.HNSubscribeService(repos.RedisPubSubRepository(REDIS_URL))
    sub_service.unsubscribe(topic, repos.Subscriber(id=query.message.chat_id))

    query.edit_message_text(f"Unsubscribed {sub_service.list_topic()[topic]} !")
    return ConversationHandler.END


def publish_topstories(context: CallbackContext):
    (
        services.NHPublishService(
            hn_repo=repos.HNRepository(),
            pubsub_repo=repos.RedisPubSubRepository(REDIS_URL),
        )
        .add_handler(Topic.top, TopStoriesEventHandler(context.bot))
        .publish_stories(Topic.top)
    )


def publish_beststories(context: CallbackContext):
    (
        services.NHPublishService(
            hn_repo=repos.HNRepository(),
            pubsub_repo=repos.RedisPubSubRepository(REDIS_URL),
        )
        .add_handler(Topic.best, BestStoriesEventHandler(context.bot))
        .publish_stories(Topic.best)
    )


def main() -> None:
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
            entry_points=[CommandHandler("subscribe", list_topic)],
            states={
                SubscribeState.FIRST: [
                    CallbackQueryHandler(
                        partial(subscribe, topic=Topic.top),
                        pattern=f"^{Topic.top}$",
                    ),
                    CallbackQueryHandler(
                        partial(subscribe, topic=Topic.best),
                        pattern=f"^{Topic.best}$",
                    ),
                ]
            },
            fallbacks=[CommandHandler("subscribe", list_topic)],
        )
    )
    dispatcher.add_handler(
        ConversationHandler(
            entry_points=[
                CommandHandler(
                    "list_subscribed",
                    list_subscribed_topic,
                )
            ],
            states={
                UnSubscribeState.FIRST: [
                    CallbackQueryHandler(
                        partial(unsubscribe, topic=Topic.top),
                        pattern=f"^{Topic.top}$",
                    ),
                    CallbackQueryHandler(
                        partial(unsubscribe, topic=Topic.best),
                        pattern=f"^{Topic.best}$",
                    ),
                ]
            },
            fallbacks=[
                CommandHandler(
                    "list_subscribed",
                    list_subscribed_topic,
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
        publish_topstories,
        interval=timedelta(seconds=30),
        name="publish_topstories",
    )
    job_queue.run_repeating(
        publish_beststories,
        interval=timedelta(seconds=30),
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
