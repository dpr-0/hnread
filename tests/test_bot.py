from time import time

from bot import BestStoriesEventHandler, TopStoriesEventHandler
from hnread import items, repos


def test_top_story_display():
    class MockBot:
        def send_message(self, id: int, text: str):
            assert "Top" in text

    handler = TopStoriesEventHandler(MockBot())
    handler.handle(
        [repos.Subscriber(id=0)],
        items.Story(
            id=0, title="", type=items.Type.story, time=time(), descendants=0, score=0
        ),
    )


def test_top_story_display():
    class MockBot:
        def send_message(self, id: int, text: str, parse_mode: str):
            assert "Best" in text

    handler = BestStoriesEventHandler(MockBot())
    handler.handle(
        [repos.Subscriber(id=0)],
        items.Story(
            id=0, title="", type=items.Type.story, time=time(), descendants=0, score=0
        ),
    )
