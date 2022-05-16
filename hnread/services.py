from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from . import items, repos
from .topics import Topic

logger = logging.getLogger(__name__)


class EventHandler(ABC):
    @abstractmethod
    def handle(
        self,
        subscribers: List[repos.Subscriber],
        item: Any,
    ):
        pass


class HNSubscribeService:
    def __init__(self, pubsub_repo: repos.IPubSubRepository) -> None:
        self.pubsub_repo = pubsub_repo

    def subscribe(self, topic: Topic, subscriber: repos.Subscriber) -> bool:
        self.pubsub_repo.set_topic(topic)
        self.pubsub_repo.add_subscriber(subscriber.id)
        return True

    def unsubscribe(self, topic: Topic, subscriber: repos.Subscriber) -> bool:
        self.pubsub_repo.set_topic(topic)
        self.pubsub_repo.remove_subscriber(subscriber.id)
        return True

    def list_topic(self) -> Dict[Topic, str]:
        return {Topic.top: "Top Stories", Topic.best: "Best Stories"}

    def list_subscribed_topic(self, chat_id: int) -> Dict[Topic, str]:
        subscribed_topics = self.pubsub_repo.subscribed_topics(chat_id)
        all_topics = self.list_topic()
        res = {}
        for topic in subscribed_topics:
            res[topic] = all_topics[topic]
        return res


class NHPublishService:
    def __init__(
        self, hn_repo: repos.HNRepository, pubsub_repo: repos.IPubSubRepository
    ) -> None:
        self.hn_repo = hn_repo
        self.pubsub_repo = pubsub_repo
        self.handlers: Dict[Topic, EventHandler] = {}
        self.stories = {
            Topic.top: self.hn_repo.topstories_id,
            Topic.best: self.hn_repo.beststories_id,
        }

    def add_handler(self, topic: Topic, handler: EventHandler) -> NHPublishService:
        self.handlers[topic] = handler
        return self

    def publish_stories(self, topic: Topic):
        stories_ids = self.stories[topic]()

        self.pubsub_repo.set_topic(topic)

        unpublished_stories_ids = self.pubsub_repo.has_not_published(stories_ids)
        unpublished_stories = self.hn_repo.ofIds(*unpublished_stories_ids, sort=True)
        unpublished_stories = list(
            filter(
                lambda item: datetime.now(timezone.utc) - item.time
                <= timedelta(days=1),
                unpublished_stories,
            )
        )
        logger.info(
            f"Found {len(unpublished_stories)} unpublished {topic.name} stories"
        )
        subscribers = self.pubsub_repo.get_subscribers()

        for story in unpublished_stories:
            handler = self.handlers[topic]
            handler.handle(subscribers, story)

        self.pubsub_repo.mark_published(unpublished_stories_ids)


class BackgroundService:
    def __init__(
        self, hn_repo: repos.HNRepository, pubsub_repo: repos.IPubSubRepository
    ) -> None:
        self.hn_repo = hn_repo
        self.pubsub_repo = pubsub_repo

    def reduce_published_set_size(self, topic: Topic):
        self.pubsub_repo.set_topic(topic)
        ids = self.pubsub_repo.get_published()
        abandoned_items = items.PublishedItems(
            self.hn_repo.ofIds(*ids)
        ).abandoned_items()
        if abandoned_items:
            logger.info(f"Reduce {len(abandoned_items)} {topic} published items")
            self.pubsub_repo.delete_published([i.id for i in abandoned_items])
