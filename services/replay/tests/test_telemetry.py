"""The replay traces its work for Application Insights: a span per moment explained and per
partner localisation, with what was decided, never the words themselves."""

from functools import cache

import anyio
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from fourth_official_match_data import demo_store
from fourth_official_replay import FeedLog, replay
from test_partners import no_wait, partners, template_only

EXPORTER = InMemorySpanExporter()


@cache
def spans() -> tuple[ReadableSpan, ...]:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
    trace.set_tracer_provider(provider)
    log = FeedLog("m42")
    anyio.run(
        lambda: replay(
            demo_store().record("m42"), log, template_only, sleep=no_wait, partners=partners()
        )
    )
    return tuple(EXPORTER.get_finished_spans())


def named(name: str) -> list[ReadableSpan]:
    return [s for s in spans() if s.name == name]


def test_every_moment_explained_is_a_span_with_how_it_was_written() -> None:
    explained = named("explain moment")

    assert explained
    for span in explained:
        attributes = dict(span.attributes or {})
        assert attributes["fourth_official.match_id"] == "m42"
        assert str(attributes["fourth_official.moment_id"]).startswith("mo-m42-")
        assert attributes["fourth_official.written_by"] == "template"
        assert attributes["fourth_official.attempts"] == 1


def test_every_partner_localisation_is_a_span_inside_its_moment() -> None:
    localized = named("localize")
    moments = {s.context.span_id for s in named("explain moment")}

    assert {s.attributes["fourth_official.tenant_id"] for s in localized} == {  # type: ignore[index]
        "northlight-sport",
        "tribuna-austral",
        "rheinblick-sport",
    }
    assert all(s.parent is not None and s.parent.span_id in moments for s in localized)


def test_no_span_carries_words() -> None:
    for span in spans():
        for value in (span.attributes or {}).values():
            assert not (isinstance(value, str) and " " in value), (span.name, value)
