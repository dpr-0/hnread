from unittest import IsolatedAsyncioTestCase, TestCase

from hnread import repos


class HNRepositoryTest(TestCase):
    def setUp(self) -> None:
        self.repo = repos.HNRepository()

    def test_get_max_id(self):
        assert self.repo.max_id()

    def test_get_item(self):
        max_id = self.repo.max_id()
        item = self.repo.ofId(max_id)
        assert item

    def test_get_beststories_id(self):
        assert self.repo.beststories_id()

    def test_get_topstories_id(self):
        assert self.repo.topstories_id()

    def test_get_newstories_id(self):
        assert self.repo.newstories_id()

    def test_get_showstories_id(self):
        assert self.repo.showstories_id()

    def test_get_jobstories_id(self):
        assert self.repo.jobstories_id()

    def test_updates_id(self):
        assert self.repo.updates_id()


class HNRepositoryAsyncTest(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.repo = repos.HNRepository()

    async def test_async_get_item(self):
        max_id = self.repo.max_id()
        item = await self.repo.aofId(max_id)
        assert item.id
