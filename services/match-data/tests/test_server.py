"""The MCP server speaks the protocol: read-only tools with schemas, structured results."""

from collections.abc import Awaitable, Callable
from typing import Any

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult

from fourth_official_match_data import __main__ as entry
from fourth_official_match_data import create_server, demo_store

EXPECTED_TOOLS = {
    "list_matches",
    "get_match_state",
    "get_metric",
    "compare_windows",
    "get_events",
    "get_player",
    "list_moments",
}


def with_client[T](action: Callable[[ClientSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with create_connected_server_and_client_session(
            create_server(demo_store())
        ) as client:
            return await action(client)

    return anyio.run(run)


def test_every_tool_is_listed_read_only_with_an_input_schema() -> None:
    listed = with_client(lambda client: client.list_tools())

    assert {t.name for t in listed.tools} == EXPECTED_TOOLS
    for tool in listed.tools:
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.openWorldHint is False
        assert tool.description
        assert tool.inputSchema["type"] == "object"


def test_a_tool_call_returns_structured_content() -> None:
    result = with_client(lambda client: client.call_tool("get_match_state", {"match_id": "m42"}))

    assert not result.isError
    content: dict[str, Any] = result.structuredContent or {}
    assert content["matchId"] == "m42"
    assert content["score"] == {"home": 2, "away": 1}


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("get_match_state", {"match_id": "m99"}),
        ("get_match_state", {"match_id": "'; DROP TABLE"}),
        ("get_metric", {"match_id": "m42", "metric": "vibes", "scope": "HCY", "window": "5m"}),
        ("get_metric", {"match_id": "m42", "metric": "xg", "scope": "SLT", "window": "5m"}),
        ("get_events", {"match_id": "m42", "from_seq": 0, "to_seq": 10}),
        ("get_player", {"match_id": "m42", "player_id": "KBA-01"}),
    ],
)
def test_bad_arguments_are_errors_not_crashes(name: str, arguments: dict[str, Any]) -> None:
    async def call(client: ClientSession) -> CallToolResult:
        return await client.call_tool(name, arguments)

    assert with_client(call).isError


def test_every_tool_answers_through_the_protocol() -> None:
    calls: list[tuple[str, dict[str, Any]]] = [
        ("list_matches", {}),
        ("get_metric", {"match_id": "m42", "metric": "xg", "scope": "HCY", "window": "match"}),
        ("compare_windows", {"match_id": "m42", "metric": "pressing_intensity", "scope": "NGT"}),
        ("get_events", {"match_id": "m42", "from_seq": 1, "to_seq": 5, "types": ["PASS"]}),
        ("get_player", {"match_id": "m42", "player_id": "HCY-01"}),
        ("list_moments", {"match_id": "m42"}),
    ]

    async def call_all(client: ClientSession) -> list[CallToolResult]:
        return [await client.call_tool(name, arguments) for name, arguments in calls]

    assert [r.isError for r in with_client(call_all)] == [False] * len(calls)


def test_the_command_line_serves_stdio_or_loopback_http(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[tuple[str, str, int]] = []

    def fake_run(self: FastMCP, transport: str) -> None:
        served.append((transport, self.settings.host, self.settings.port))

    monkeypatch.setattr(FastMCP, "run", fake_run)
    entry.main([])
    entry.main(["--http", "--port", "8123"])

    assert served[0][0] == "stdio"
    assert served[1] == ("streamable-http", "127.0.0.1", 8123)
