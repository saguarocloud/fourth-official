"""Every tool call stays inside the moment being explained, whatever the agent asks for."""

from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from pydantic import BaseModel

from fourth_official_explain.bounds import MomentBound, bounded_arguments


@pytest.mark.parametrize(
    ("name", "asked", "bounded"),
    [
        ("get_match_state", {"match_id": "m42"}, {"match_id": "m42", "as_of_seq": 287}),
        ("get_metric", {"as_of_seq": 2000}, {"as_of_seq": 287}),
        ("get_metric", {"as_of_seq": 100}, {"as_of_seq": 100}),
        ("compare_windows", {"as_of_seq": None}, {"as_of_seq": 287}),
        ("get_events", {"from_seq": 1, "to_seq": 5000}, {"from_seq": 1, "to_seq": 287}),
        ("get_events", {"from_seq": 900, "to_seq": 950}, {"from_seq": 287, "to_seq": 287}),
        ("get_events", {"from_seq": 10, "to_seq": 20}, {"from_seq": 10, "to_seq": 20}),
    ],
)
def test_arguments_are_clamped_to_the_moment(
    name: str, asked: dict[str, Any], bounded: dict[str, Any]
) -> None:
    assert bounded_arguments(name, asked, 287) == bounded


class Arguments(BaseModel):
    match_id: str
    as_of_seq: int | None = None


def test_the_middleware_rewrites_arguments_before_the_call_runs() -> None:
    seen: list[object] = []
    context = SimpleNamespace(
        function=SimpleNamespace(name="get_metric"),
        arguments=Arguments(match_id="m42", as_of_seq=999),
    )

    async def call_next() -> None:
        seen.append(context.arguments)

    anyio.run(MomentBound(287).process, context, call_next)  # type: ignore[arg-type]

    assert seen == [{"match_id": "m42", "as_of_seq": 287}]
