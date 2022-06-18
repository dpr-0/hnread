import logging
from abc import ABC, abstractmethod
from queue import PriorityQueue
from statistics import NormalDist, StatisticsError, mean, variance
from typing import Callable, List

from hnread.items import ScoreableItem

logger = logging.getLogger(__name__)


class AbstractFilter(ABC):
    @abstractmethod
    def __call__(self, items: List[ScoreableItem]) -> List[ScoreableItem]:
        pass


class NormalDistributionFilter(AbstractFilter):
    def __init__(self, capacity: int = 100, threshold: float = 0.5) -> None:
        self.q: PriorityQueue = PriorityQueue(maxsize=capacity)
        self.threshold = threshold

    def add(self, item: ScoreableItem):
        if self.q.full():
            self.q.get()
        self.q.put((item.time.timestamp(), item))

    def set_threshold(self, threshold: float):
        self.threshold = threshold

    def __call__(self, items: List[ScoreableItem]) -> List[ScoreableItem]:
        for item in items:
            self.add(item)

        logger.info(f"Filter queue has {len(self.q.queue)} data")

        nums = [item.score for _, item in self.q.queue]

        try:
            rv = NormalDist(mu=mean(nums), sigma=variance(nums))
        except StatisticsError:
            return items
        else:
            threshold_func: Callable[[ScoreableItem], bool] = (
                lambda item: rv.cdf(item.score) > self.threshold
            )
            return list(filter(threshold_func, items))


norm_filter = NormalDistributionFilter()
