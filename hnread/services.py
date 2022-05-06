from __future__ import annotations

import logging
from abc import ABC
from typing import Dict, List

from typing_extensions import Self

from . import repos
from .topics import Topic

logger = logging.getLogger(__name__)


class EventHandler(ABC):
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

    def unpublished_stories_ids(self, topic: Topic) -> List[int]:
        stories_ids = self.stories[topic]()
        unpublished_stories_ids = self.pubsub_repo.set_topic(topic).has_not_published(
            stories_ids
        )
        logger.info(
            f"Found {len(unpublished_stories_ids)} unpublished {topic.name} stories"
        )
        return unpublished_stories_ids

    def add_handler(self, topic: Topic, handler: EventHandler) -> NHPublishService:
        self.handlers[topic] = handler
        return self

    def publish_stories(self, topic: Topic):
        unpublished_stories_ids = self.unpublished_stories_ids(topic)
        unpublished_stories = self.hn_repo.ofIds(*unpublished_stories_ids, sort=True)
        self.pubsub_repo.set_topic(topic)
        subscribers = self.pubsub_repo.get_subscribers()
        for story in unpublished_stories:
            handler = self.handlers[topic]
            handler.handle(subscribers, story)
            self.pubsub_repo.mark_published(story.id)
