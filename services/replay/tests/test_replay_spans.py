"""The replay traces its work for Application Insights: a span per moment explained and per
partner localisation, with what was decided, never the words themselves."""

import dataclasses
import re
from functools import cache

import anyio
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from fourth_official_contracts import Moment
from fourth_official_explain import Explanation, explain
from fourth_official_explain.pipeline import Attempt
from fourth_official_match_data import demo_store
from fourth_official_replay import FeedLog, replay
from fourth_official_verifier import MatchFacts
from test_partners import no_wait, partners, template_only

EXPORTER = InMemorySpanExporter()


@cache
def spans() -> tuple[ReadableSpan, ...]:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
    trace.set_tracer_provider(provider)

    async def both() -> None:
        store = demo_store()
        await replay(
            store.record("m42"), FeedLog("m42"), template_only, sleep=no_wait, partners=partners()
        )
        await replay(store.record("m43"), FeedLog("m43"), drafted, sleep=no_wait)

    anyio.run(both)
    return tuple(EXPORTER.get_finished_spans())


async def drafted(moment: Moment, facts: MatchFacts) -> Explanation:
    """The template's insight, as if the fallback model wrote it after the fast one timed out."""
    explanation = await explain(moment, facts, [])
    tried = (
        Attempt(1, "analyst", "fast", "error", error="TimeoutError"),
        dataclasses.replace(explanation.attempts[-1], number=2, agent="analyst", model="fallback"),
    )
    return dataclasses.replace(explanation, attempts=tried)


def named(name: str) -> list[ReadableSpan]:
    return [s for s in spans() if s.name == name]


def of(match_id: str, spans: list[ReadableSpan]) -> list[ReadableSpan]:
    return [s for s in spans if (s.attributes or {}).get("fourth_official.match_id") == match_id]


def test_every_moment_explained_is_a_span_with_how_it_was_written() -> None:
    explained = of("m42", named("explain moment"))

    assert explained
    for span in explained:
        attributes = dict(span.attributes or {})
        assert attributes["fourth_official.match_id"] == "m42"
        assert str(attributes["fourth_official.moment_id"]).startswith("mo-m42-")
        assert attributes["fourth_official.written_by"] == "template"
        assert attributes["fourth_official.attempts"] == 1


def test_a_moment_a_model_wrote_names_the_model_and_its_failures() -> None:
    drafted_spans = of("m43", named("explain moment"))

    assert drafted_spans
    for span in drafted_spans:
        attributes = dict(span.attributes or {})
        assert attributes["fourth_official.written_by"] == "fallback"
        assert attributes["fourth_official.model_errors"] == 1
        assert attributes["fourth_official.attempts"] == 2


def test_every_partner_localisation_is_a_span_inside_its_moment() -> None:
    localized = named("localize")
    moments = {s.context.span_id for s in named("explain moment")}

    assert {s.attributes["fourth_official.tenant_id"] for s in localized} == {  # type: ignore[index]
        "northlight-sport",
        "tribuna-austral",
        "rheinblick-sport",
    }
    assert all(s.parent is not None and s.parent.span_id in moments for s in localized)


IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


def test_no_span_carries_words_only_identifiers_counts_and_flags() -> None:
    for span in spans():
        for value in (span.attributes or {}).values():
            assert isinstance(value, bool | int) or IDENTIFIER.match(str(value)), (span.name, value)
