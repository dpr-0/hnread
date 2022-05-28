from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, HttpUrl


class Type(str, Enum):
    """
    The type of item. One of "job", "story", "comment", "poll", or "pollopt".
    """

    job = "job"
    story = "story"
    comment = "comment"
    poll = "poll"
    pollopt = "pollopt"


class Item(BaseModel):
    id: int
    type: Type
    by: Optional[str]  # The username of the item's author.
    time: datetime  # Creation date of the item, in Unix Time.


class DeletedItem(Item):
    deleted: bool  # true if the item is deleted.


class DeadItem(Item):
    dead: bool  # true if the item is dead.


class Story(Item):
    title: str  # The title of the story, poll or job. HTML.
    descendants: int  # In the case of stories or polls, the total comment count.
    kids: List[int] = []  # The ids of the item's comments, in ranked display order.
    score: int  # The story's score, or the votes for a pollopt.
    url: Optional[HttpUrl]  # The URL of the story.
    text: Optional[str]


class Comment(Item):
    parent: int  # The comment's parent: either another comment or the relevant story.
    kids: List[int] = []
    text: str  # The comment, story or poll text. HTML.


class Job(Item):
    title: str
    text: Optional[str]
    url: Optional[HttpUrl]
    score: int


class Poll(Item):
    title: str
    text: Optional[str]
    descendants: int
    score: int
    parts: List[int] = []  # A list of related pollopts, in display order.
    kids: List[int] = []


class PollOpt(Item):
    poll: int
    text: str
    score: int


class ObjectNotDefinedError(Exception):
    pass


class ItemFactory:
    def from_dict(
        self, data: dict
    ) -> Union[DeletedItem, DeadItem, Story, Comment, Job, Poll, PollOpt]:

        if data.get("deleted"):
            return DeletedItem(**data)
        elif data.get("dead"):
            return DeadItem(**data)

        item_type = data["type"]
        if item_type == Type.story:
            return Story(**data)
        elif item_type == Type.comment:
            return Comment(**data)
        elif item_type == Type.job:
            return Job(**data)
        elif item_type == Type.poll:
            return Poll(**data)
        elif item_type == Type.pollopt:
            return PollOpt(**data)
        else:
            raise ObjectNotDefinedError(f"{data}")


class PublishedItems:
    def __init__(self, items: List[Item]) -> None:
        self.items = sorted(items, key=lambda items: items.time)

    def abandoned_items(self) -> List[Item]:
        res = []
        for item in self.items:
            if datetime.now(timezone.utc) - item.time < timedelta(days=5):
                break
            res.append(item)
        return res


class ItemDisplay(ABC):
    @abstractmethod
    def __str__(self) -> str:
        pass

    @abstractmethod
    def topic(self) -> str:
        pass


class StoryDisplay(ItemDisplay):
    def __init__(self, item: Union[Story, Job, Poll]) -> None:
        self.item = item

    def __str__(self) -> str:
        points = self.item.score
        title = self.item.title
        url = self.url()
        num_comments = self.num_comments()
        topic = self.topic()

        fixed_width_text = (
            f"{points} points | {num_comments} comments | {topic} | {self.time_age()}"
        )
        text = (
            f'<a href="{url}"><b>{title}</b></a>\n'
            f'<a href="{self.hn_url()}">{fixed_width_text}</a>\n'
        )
        return text

    def url(self) -> str:
        if (url := getattr(self.item, "url", None)) is not None:
            return url
        else:
            return self.hn_url()

    def hn_url(self) -> str:
        return f"https://news.ycombinator.com/item?id={self.item.id}"

    def num_comments(self) -> int:
        if (num_comments := getattr(self.item, "descendants", None)) is not None:
            return num_comments
        else:
            return 0

    def time_age(self) -> str:
        time_ago = datetime.now(tz=timezone.utc) - self.item.time
        hours = time_ago.seconds // 3600
        if time_ago.days > 1:
            return f"{time_ago.days} days ago"
        elif time_ago.days == 1:
            return f"{time_ago.days} day ago"
        elif hours > 1:
            return f"{hours} hours ago"
        elif hours == 1:
            return f"{hours} hour ago"
        return ""


class TopStoryDisplay(StoryDisplay):
    def topic(self) -> str:
        return "Top"


class BestStoryDisplay(StoryDisplay):
    def topic(self) -> str:
        return "Best"
