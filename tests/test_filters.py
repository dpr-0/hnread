from datetime import datetime
from unittest import TestCase

from hnread import filters
from hnread.items import ScoreableItem, Type


class TestNormalDistributionFilter(TestCase):
    def test(self):
        f = filters.NormalDistributionFilter(capacity=10)

        items = [
            ScoreableItem(id=0, type=Type.story, time=datetime.utcnow(), score=score)
            for score in range(15)
        ]
        res = f(items)
        assert len(res) == 5
