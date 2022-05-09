from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from itertools import compress
from typing import List, Tuple

import httpx
import redis
from pydantic import BaseModel

from . import items
from .topics import Topic


class HNRepository:
    def __init__(self) -> None:
        self.domain = "hacker-news.firebaseio.com"
        self.base_url = f"https://{self.domain}/v0"
        self.item_factory = items.ItemFactory()

    def _get_resource(self, resource_name: str) -> httpx.Response:
        return httpx.get(f"{self.base_url}/{resource_name}.json")

    async def _aget_resource(self, resource_name: str) -> httpx.Response:
        async with httpx.AsyncClient() as client:
            return await client.get(f"{self.base_url}/{resource_name}.json")

    def ofId(self, id: int) -> items.Item:
        resp = self._get_resource(f"item/{id}")
        item = self.item_factory.from_dict(resp.json())
        return item

    async def aofId(self, id: int) -> items.Item:
        resp = await self._aget_resource(f"item/{id}")
        item = self.item_factory.from_dict(resp.json())
        return item

    def ofIds(self, *ids: int, sort: bool = False) -> List[items.Item]:
        tasks = [self.aofId(i) for i in ids]

        async def f():
            return await asyncio.gather(*tasks)

        items = asyncio.run(f())

        if sort:
            items = sorted(items, key=lambda items: items.time)
        return items

    def max_id(self) -> int:
        resp = self._get_resource("maxitem")
        return int(resp.text)

    def beststories_id(self) -> List[int]:
        """ """
        return self._get_resource("beststories").json()

    def topstories_id(self) -> List[int]:
        """
        Up to 500 top and new stories
        """
        topstories = self._get_resource("topstories").json()
        newstories = self.newstories_id()
        real_topstories = list(set(topstories) - set(newstories))
        return real_topstories

    def newstories_id(self) -> List[int]:
        """ """
        return self._get_resource("newstories").json()

    def askstories_id(self) -> List[int]:
        """
        Up to 200 of the latest Ask HN Stories
        """
        return self._get_resource("askstories").json()

    def showstories_id(self) -> List[int]:
        """
        Up to 200 of the latest Show HN Stories!
        """
        return self._get_resource("showstories").json()

    def jobstories_id(self) -> List[int]:
        """
        Up to 200 of the latest Job Stories!
        """
        return self._get_resource("jobstories").json()

    def updates_id(self) -> Tuple[List[int], List[str]]:
        """
        The item and profile changes are at
        https://hacker-news.firebaseio.com/v0/updates.
        """
        return self._get_resource("updates").json()


class Subscriber(BaseModel):
    id: int


class IPubSubRepository(ABC):
    @abstractmethod
    def flush(self):
        pass

    @abstractmethod
    def set_topic(self, topic: Topic) -> IPubSubRepository:
        pass

    @abstractmethod
    def has_published(self, ids: List[int]) -> List[int]:
        pass

    @abstractmethod
    def has_not_published(self, ids: List[int]) -> List[int]:
        pass

    @abstractmethod
    def mark_published(self, ids: List[int]):
        pass
        pass

    @abstractmethod
    def empty_published(self) -> bool:
        pass

    @abstractmethod
    def add_subscriber(self, id: int):
        pass

    @abstractmethod
    def remove_subscriber(self, id: int):
        pass

    @abstractmethod
    def get_subscribers(self) -> List[Subscriber]:
        pass

    @abstractmethod
    def subscribed_topics(self, id: int) -> List[Topic]:
        pass


class RedisPubSubRepository(IPubSubRepository):
    def __init__(self, url: str, topic: Topic = None) -> None:
        self.topic = topic
        self.r = redis.Redis.from_url(url)

    def flush(self):
        self.r.flushdb()

    def _published_set_key(self) -> str:
        return f"{self.topic}:published"

    def _topic_subscribers_set_key(self) -> str:
        return f"{self.topic}:subscribers"

    def _user_subscribed_topics_list_key(self, id: int) -> str:
        return f"chat_id:{id}:subscribed:topics"

    def set_topic(self, topic: Topic) -> RedisPubSubRepository:
        self.topic = topic
        return self

    def _has_published(self, ids: List[int]) -> List[bool]:
        return self.r.smismember(self._published_set_key(), ids)

    def has_published(self, ids: List[int]) -> List[int]:
        published_selectors = self._has_published(ids)
        return list(compress(ids, published_selectors))

    def has_not_published(self, ids: List[int]) -> List[int]:
        published_selectors = self._has_published(ids)
        unpublished_selectors = [not b for b in published_selectors]
        return list(compress(ids, unpublished_selectors))

    def mark_published(self, ids: List[int]):
        if not ids:
            return
        self.r.sadd(self._published_set_key(), *ids)

    def empty_published(self) -> bool:
        return self.r.exists(self._published_set_key()) == 0

    def add_subscriber(self, id: int):
        self.r.sadd(self._user_subscribed_topics_list_key(id), f"{self.topic}")
        self.r.sadd(self._topic_subscribers_set_key(), id)

    def remove_subscriber(self, id: int):
        self.r.srem(self._user_subscribed_topics_list_key(id), f"{self.topic}")
        self.r.srem(self._topic_subscribers_set_key(), id)

    def get_subscribers(self) -> List[Subscriber]:
        subscribers = []
        for subscriber_id in self.r.smembers(self._topic_subscribers_set_key()):
            subscribers.append(Subscriber(id=subscriber_id.decode()))
        return subscribers

    def subscribed_topics(self, id: int) -> List[Topic]:
        subscribed_topics = []
        for topic in self.r.smembers(self._user_subscribed_topics_list_key(id)):
            subscribed_topics.append(Topic(topic.decode()))
        return subscribed_topics
