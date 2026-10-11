"""Every tool call stays inside the moment being explained, whatever the agent asks for."""

from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult
from pydantic import BaseModel

from fourth_official_explain.bounds import MomentBound, bounded_arguments
from fourth_official_match_data import create_server, demo_store


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
        ("get_player", {"player_id": "HCY-01"}, {"player_id": "HCY-01"}),
        ("list_moments", {}, {"as_of_seq": 287}),
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


CALLS: list[tuple[str, dict[str, Any]]] = [
    ("get_match_state", {"match_id": "m42", "as_of_seq": 5000}),
    ("get_metric", {"match_id": "m42", "metric": "xg", "scope": "HCY", "window": "match"}),
    ("compare_windows", {"match_id": "m42", "metric": "pressing_intensity", "scope": "NGT"}),
    ("get_events", {"match_id": "m42", "from_seq": 1, "to_seq": 5000}),
    ("get_player", {"match_id": "m42", "player_id": "HCY-01"}),
    ("list_moments", {"match_id": "m42"}),
]


@pytest.mark.parametrize(("name", "arguments"), CALLS)
def test_the_real_server_accepts_every_bounded_call(name: str, arguments: dict[str, Any]) -> None:
    server = create_server(demo_store())

    async def call() -> CallToolResult:
        async with create_connected_server_and_client_session(server) as client:
            return await client.call_tool(name, bounded_arguments(name, arguments, 1500))

    result = anyio.run(call)

    assert not result.isError, result.content
