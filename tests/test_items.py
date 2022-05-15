from datetime import datetime, timedelta, timezone

from hnread import items


def test_published_abandon():
    item1 = items.Item(id=0, type=items.Type.story, time=datetime.now(timezone.utc))
    item2 = items.Item(
        id=0, type=items.Type.story, time=datetime.now(timezone.utc) - timedelta(days=5)
    )
    published_items = items.PublishedItems([item1, item2])
    assert 1 == len(published_items.abandoned_items())
