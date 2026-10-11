"""The matchday API: list matches, start the replay, read or stream each match's feed."""

import asyncio
import contextlib
import json
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import anyio
import pytest
from fastapi.testclient import TestClient

from fourth_official_api import explainers, main, matchday_routes
from fourth_official_api.explainers import foundry_drafters
from fourth_official_api.main import create_app
from fourth_official_api.provenance import Issuer
from fourth_official_api.settings import FoundrySettings, Settings, StartLedgerSettings
from fourth_official_api.start_ledger import LedgerError
from fourth_official_contracts import Moment, Provenance, parse_feed_entry
from fourth_official_explain import Explanation, explain
from fourth_official_match_data import demo_store
from fourth_official_moments import detect
from fourth_official_provenance import InMemoryStore, LocalSigner
from fourth_official_replay import (
    Explainer,
    FeedLog,
    InMemoryLedger,
    Matchday,
    ReplayConfig,
    facts_for,
)
from fourth_official_verifier import MatchFacts


async def no_wait(seconds: float) -> None:
    return None


async def template_only(moment: Moment, facts: MatchFacts) -> Explanation:
    return await explain(moment, facts, [])


START = {"X-Requested-By": "fourth-official"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    day = Matchday(
        demo_store(), template_only, config=ReplayConfig(), cooldown=600.0, sleep=no_wait
    )
    with TestClient(create_app(Settings(version="test"), matchday=day)) as client:
        yield client


def start(client: TestClient) -> int:
    return client.post("/api/matchday", headers=START).status_code


def finish(client: TestClient) -> None:
    """Wait for the run on the app's own event loop: no polling, no timing."""
    assert client.portal is not None
    day: Matchday = client.app.state.matchday  # type: ignore[attr-defined]
    client.portal.call(day.wait)


def test_matches_are_listed_idle_before_the_matchday_starts(client: TestClient) -> None:
    response = client.get("/api/matches")

    assert response.status_code == 200
    matches = response.json()["matches"]
    assert [(m["matchId"], m["homeName"], m["state"]) for m in matches] == [
        ("m42", "Harbour City", "idle"),
        ("m43", "Kingsbridge Athletic", "idle"),
        ("m44", "Calder Town", "idle"),
    ]


def test_starting_the_matchday_replays_and_fills_every_feed(client: TestClient) -> None:
    assert start(client) == 202
    finish(client)
    feed = client.get("/api/matches/m42/feed").json()
    assert feed["finished"] is True
    kinds = {parse_feed_entry(e).kind for e in feed["entries"]}
    assert kinds == {"clock", "moment", "insight", "correction"}


def test_a_second_start_is_refused_while_running_or_cooling_down(client: TestClient) -> None:
    start(client)

    again = client.post("/api/matchday", headers=START)

    assert again.status_code == 409
    assert "matchday" in again.json()["detail"]


def test_availability_tells_the_studio_when_it_may_start(client: TestClient) -> None:
    before = client.get("/api/matchday")
    assert before.status_code == 200
    assert before.headers["cache-control"] == "no-store"
    assert before.json() == {
        "ready": True,
        "blockedBy": None,
        "reason": None,
        "readyAt": None,
    }

    start(client)
    finish(client)
    after = client.get("/api/matchday").json()

    assert after["ready"] is False
    assert after["blockedBy"] == "cooldown"
    assert after["reason"].startswith("the matchday can be replayed again in ")


def test_availability_says_from_when_in_utc() -> None:
    started = time.time() - 100.0
    ledger = InMemoryLedger()
    anyio.run(ledger.claim, started, lambda _: None)
    day = Matchday(demo_store(), template_only, cooldown=600.0, ledger=ledger, sleep=no_wait)

    with TestClient(create_app(Settings(version="test"), matchday=day)) as client:
        body = client.get("/api/matchday").json()

    assert body["blockedBy"] == "cooldown"
    assert body["readyAt"] == datetime.fromtimestamp(started + 600.0, UTC).isoformat()


def test_the_feed_resumes_after_the_entries_a_client_has(client: TestClient) -> None:
    start(client)
    finish(client)

    everything = client.get("/api/matches/m42/feed").json()["entries"]
    rest = client.get("/api/matches/m42/feed", params={"after": 5}).json()["entries"]

    assert rest == everything[5:]
    assert client.get("/api/matches/m42/feed").headers["cache-control"] == "no-store"


def test_the_stream_sends_every_entry_as_a_server_sent_event(client: TestClient) -> None:
    start(client)
    finish(client)

    with client.stream(
        "GET", "/api/matches/m43/stream", headers={"Last-Event-ID": "1:3"}
    ) as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        events = [e for e in stream.iter_text() for e in e.split("\n\n") if e.startswith("id:")]

    ids = [int(e.split("\n")[0].removeprefix("id: 1:")) for e in events]
    assert ids[0] == 4
    assert ids == sorted(ids)
    first = json.loads(events[0].split("data: ", 1)[1])
    assert parse_feed_entry(first).entry_seq == 4


@pytest.mark.parametrize(
    "path",
    ["/api/matches/m99/feed", "/api/matches/m99/stream", "/api/matches/nope/feed"],
)
def test_unknown_matches_are_not_found(client: TestClient, path: str) -> None:
    assert client.get(path).status_code in {404, 422}


def test_feed_parameters_are_validated(client: TestClient) -> None:
    assert client.get("/api/matches/m42/feed", params={"after": -1}).status_code == 422
    assert client.get("/api/matches/m42/feed", params={"after": "x"}).status_code == 422


def test_without_foundry_the_api_starts_with_template_explanations() -> None:
    with TestClient(create_app(Settings(version="test"))) as client:
        assert client.get("/api/matches").status_code == 200


def test_with_foundry_configured_the_api_opens_the_analyst_at_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []

    @asynccontextmanager
    async def fake(settings: FoundrySettings) -> AsyncIterator[Explainer]:
        opened.append(settings.project_endpoint)
        yield template_only
        opened.append("closed")

    monkeypatch.setattr(main, "foundry_explainer", fake)
    foundry = FoundrySettings(
        project_endpoint="https://ais-abc.services.ai.azure.com/api/projects/p",
        match_data_url="http://127.0.0.1:8100/mcp",
        client_id="",
    )

    app = main.create_app(
        Settings(version="test", foundry=foundry),
        ledger=InMemoryLedger(),
        provenance=local_issuer(),
    )
    with TestClient(app) as client:
        assert client.get("/api/matches").status_code == 200

    assert opened == [foundry.project_endpoint, "closed"]


def test_a_configured_start_ledger_is_opened_at_startup_and_lets_the_analyst_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []

    @asynccontextmanager
    async def fake_explainer(settings: FoundrySettings) -> AsyncIterator[Explainer]:
        yield template_only

    @asynccontextmanager
    async def fake_ledger(url: str, client_id: str) -> AsyncIterator[InMemoryLedger]:
        opened.append(url)
        yield InMemoryLedger()
        opened.append("closed")

    monkeypatch.setattr(main, "foundry_explainer", fake_explainer)
    monkeypatch.setattr(main, "blob_start_ledger", fake_ledger)
    settings = Settings(
        version="test",
        foundry=FoundrySettings(
            project_endpoint="https://ais-abc.services.ai.azure.com/api/projects/p",
            match_data_url="http://127.0.0.1:8100/mcp",
            client_id="",
        ),
        start_ledger=StartLedgerSettings(url="https://st.blob.core.windows.net/c/b", client_id=""),
        runs_per_day=6,
    )

    with TestClient(main.create_app(settings, provenance=local_issuer())) as client:
        assert client.get("/api/matchday").json()["ready"] is True
        day: Matchday = client.app.state.matchday  # type: ignore[attr-defined]
        assert day.runs_per_day == 6

    assert opened == ["https://st.blob.core.windows.net/c/b", "closed"]


def test_the_foundry_explainer_builds_the_fast_then_fallback_analysts() -> None:
    foundry = FoundrySettings(
        project_endpoint="https://ais-abc.services.ai.azure.com/api/projects/p",
        match_data_url="http://127.0.0.1:8100/mcp",
        client_id="",
    )

    drafters = foundry_drafters(foundry, credential=FakeCredential())  # type: ignore[arg-type]

    assert [d.provenance.model for d in drafters] == ["fast", "fallback"]
    assert drafters[0].options == {"reasoning": {"effort": "minimal"}}
    assert drafters[1].options == {}


class FakeCredential:
    async def get_token(self, *scopes: str, **kwargs: object) -> object:
        raise AssertionError("no token may be requested")

    async def close(self) -> None: ...

    async def __aenter__(self) -> "FakeCredential":
        return self

    async def __aexit__(self, *exc: object) -> None: ...


def test_the_foundry_explainer_opens_its_credential_and_drafters_and_explains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []

    class FakeDrafter:
        provenance = Provenance(
            agent="analyst", prompt_version="v1.1", model="fast", produced_by="model"
        )

        async def __aenter__(self) -> "FakeDrafter":
            log.append("open")
            return self

        async def __aexit__(self, *exc: object) -> None:
            log.append("close")

        async def draft(self, request: object) -> object:
            raise RuntimeError("service unavailable")

    monkeypatch.setattr(explainers, "DefaultAzureCredential", lambda **_: FakeCredential())
    monkeypatch.setattr(
        explainers, "foundry_drafters", lambda settings, credential: [FakeDrafter()]
    )
    foundry = FoundrySettings(
        project_endpoint="https://ais-abc.services.ai.azure.com/api/projects/p",
        match_data_url="http://127.0.0.1:8100/mcp",
        client_id="00000000-0000-0000-0000-000000000001",
    )
    record = demo_store().record("m42")
    goal = next(m for m in detect(record.match)[1] if m.kind == "goal")

    async def run() -> Explanation:
        async with explainers.foundry_explainer(foundry) as explainer:
            return await explainer(goal, facts_for(record))

    explained = anyio.run(run)

    assert log == ["open", "close"]
    assert [a.outcome for a in explained.attempts] == ["error", "passed"]
    assert explained.insight is not None


def test_the_template_explainer_needs_no_model() -> None:
    record = demo_store().record("m42")
    goal = next(m for m in detect(record.match)[1] if m.kind == "goal")

    explained = anyio.run(explainers.template_explainer, goal, facts_for(record))

    assert explained.verdict.passed


def test_an_idle_stream_sends_heartbeats(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(matchday_routes, "HEARTBEAT_SECONDS", 0.01)

    async def first_chunk() -> str:
        events = matchday_routes.events(FeedLog("m42"), 0, 0)
        try:
            return await anext(events)
        finally:
            await events.aclose()

    assert anyio.run(first_chunk) == ": keep-alive\n\n"


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Requested-By": "someone"}, {**START, "Origin": "https://evil.example"}],
)
def test_starting_needs_the_studio_header_and_no_foreign_origin(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post("/api/matchday", headers=headers)

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("last_event_id", "generation", "resume"),
    [
        (None, 1, 0),
        ("1:5", 1, 5),
        ("0:5", 1, 0),
        ("abc", 1, 0),
        ("-1", 1, 0),
        ("1:99999999999", 1, 1_000_000),
    ],
)
def test_reconnecting_clients_resume_only_within_their_run(
    last_event_id: str | None, generation: int, resume: int
) -> None:
    assert matchday_routes.resume_point(last_event_id, generation) == resume


def test_a_garbled_last_event_id_still_streams_from_the_top(client: TestClient) -> None:
    start(client)
    finish(client)

    with client.stream(
        "GET", "/api/matches/m44/stream", headers={"Last-Event-ID": "abc"}
    ) as stream:
        first = next(stream.iter_text())

    assert first.startswith("id: 1:1\n")


def test_a_new_run_resets_readers_of_the_old_one() -> None:
    feed = FeedLog("m42")

    async def scenario() -> str:
        events = matchday_routes.events(feed, 0, 0, lifetime=5)
        pending = asyncio.ensure_future(anext(events))
        await asyncio.sleep(0.01)
        await feed.reset()
        try:
            return await pending
        finally:
            await events.aclose()

    assert anyio.run(scenario).startswith("event: reset\n")


def test_a_stream_ends_when_its_lifetime_is_up() -> None:
    async def drain() -> list[str]:
        return [chunk async for chunk in matchday_routes.events(FeedLog("m42"), 0, 0, lifetime=0)]

    assert anyio.run(drain) == []


def test_streams_beyond_the_limit_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(matchday_routes, "MAX_STREAMS", 0)
    day = Matchday(demo_store(), template_only, sleep=no_wait)

    with TestClient(create_app(Settings(version="test"), matchday=day)) as client:
        assert client.get("/api/matches/m42/stream").status_code == 503


def test_a_long_feed_is_paged_and_not_finished_until_the_last_page(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(matchday_routes, "MAX_ENTRIES_PER_PAGE", 10)
    start(client)
    finish(client)

    first = client.get("/api/matches/m42/feed").json()
    total = len(client.app.state.matchday.feed("m42").entries)  # type: ignore[attr-defined]
    last = client.get("/api/matches/m42/feed", params={"after": total - 5}).json()

    assert (len(first["entries"]), first["hasMore"], first["finished"]) == (10, True, False)
    assert (len(last["entries"]), last["hasMore"], last["finished"]) == (5, False, True)
    assert first["generation"] == 1


def test_a_stream_that_fails_before_it_starts_gives_its_slot_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(matchday_routes, "MAX_STREAMS", 1)
    day = Matchday(demo_store(), template_only, sleep=no_wait)
    app = create_app(Settings(version="test"), matchday=day)

    async def scenario() -> list[int]:
        app.state.matchday = day
        statuses: list[int] = []
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/matches/m42/stream",
            "headers": [],
            "query_string": b"",
            "app": app,
        }

        async def receive() -> dict[str, object]:
            return {"type": "http.disconnect"}

        async def gone(message: dict[str, object]) -> None:
            if message["type"] == "http.response.start":
                statuses.append(int(message["status"]))  # type: ignore[call-overload]
                raise OSError("client went away")

        for _ in range(3):
            with contextlib.suppress(OSError):
                await app(scope, receive, gone)  # type: ignore[arg-type]
        return statuses

    assert anyio.run(scenario) == [200, 200, 200]


def local_issuer() -> Issuer:
    """Records signed with a local key, as tests need; a deployment uses the vault key."""
    return Issuer(LocalSigner(), InMemoryStore())


def test_the_analyst_is_never_enabled_without_a_durable_start_ledger() -> None:
    foundry = FoundrySettings(
        project_endpoint="https://ais-abc.services.ai.azure.com/api/projects/p",
        match_data_url="http://127.0.0.1:8100/mcp",
        client_id="",
    )

    app = create_app(Settings(version="test", foundry=foundry))

    with pytest.raises(RuntimeError, match="durable start ledger"), TestClient(app):
        pass


def test_a_finished_run_ends_its_stream_with_an_end_event(client: TestClient) -> None:
    start(client)
    finish(client)

    with client.stream("GET", "/api/matches/m42/stream") as stream:
        chunks = list(stream.iter_text())

    assert "".join(chunks).rstrip().endswith('event: end\ndata: {"generation": 1}')


class BrokenLedger:
    async def recent(self, since: float) -> tuple[float, ...]:
        raise LedgerError("the start ledger is unavailable")

    async def claim(self, started: float, check: object) -> None:
        raise LedgerError("the start ledger is unavailable")


def test_an_unavailable_start_ledger_is_a_503_and_starts_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    day = Matchday(demo_store(), template_only, ledger=BrokenLedger(), sleep=no_wait)

    with TestClient(create_app(Settings(version="test"), matchday=day)) as client:
        availability = client.get("/api/matchday")
        started = client.post("/api/matchday", headers=START)

    for response in (availability, started):
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"detail": "the matchday cannot be started right now"}
    assert [m.state for m in day.status()] == ["idle"] * 3
    assert any("start ledger" in r.getMessage() for r in caplog.records)


def test_the_analyst_is_never_enabled_without_the_studio_s_signing_key() -> None:
    foundry = FoundrySettings(
        project_endpoint="https://ais-abc.services.ai.azure.com/api/projects/p",
        match_data_url="http://127.0.0.1:8100/mcp",
        client_id="",
    )

    # A deployment that writes with models signs with the vault key, never a throwaway one.
    app = create_app(Settings(version="test", foundry=foundry), ledger=InMemoryLedger())

    with pytest.raises(RuntimeError, match="signing key"), TestClient(app):
        pass
