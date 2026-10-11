"""A matchday whose featured match, once played, waits before full time until released: its held
items are on the feed and the feed is still open. Shared by the replay and API decision tests."""

from collections.abc import Callable

import anyio

from fourth_official_contracts import TenantItemEntry
from fourth_official_match_data import demo_store
from fourth_official_replay import Matchday, Partners, ReplayConfig
from fourth_official_replay.replay import Sleep
from test_partners import no_wait, partners, template_only


class Paused:
    def __init__(
        self, *, factory: Callable[[], Partners] = partners, sleep: Sleep = no_wait
    ) -> None:
        self.released = anyio.Event()
        self.day = Matchday(
            demo_store(),
            template_only,
            config=ReplayConfig(),
            sleep=sleep,
            partners=factory,
            cooldown=0.0,
        )
        feed = self.day.feed("m42")
        finish = feed.finish

        async def held_open() -> None:
            await self.released.wait()
            await finish()

        feed.finish = held_open  # type: ignore[method-assign]

    @property
    def generation(self) -> int:
        return self.day.feed("m42").generation

    def held(self) -> list[TenantItemEntry]:
        """Items whose latest version is held for an editor."""
        latest: dict[str, TenantItemEntry] = {}
        for entry in self.day.feed("m42").entries:
            if isinstance(entry, TenantItemEntry):
                latest[entry.overlay.item_id] = entry
        return [e for e in latest.values() if e.state == "pending_approval"]

    async def until_held(self) -> None:
        with anyio.fail_after(10):
            while not self.held():
                await anyio.sleep(0)
