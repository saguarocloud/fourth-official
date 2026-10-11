"""The MCP server speaks the protocol: read-only tools with input and output schemas, structured
results, strict arguments and errors that never repeat the input."""

from collections.abc import Awaitable, Callable
from typing import Any

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from fourth_official_match_data import __main__ as entry
from fourth_official_match_data import create_server, demo_store
from fourth_official_match_data.server import LOOPBACK

EXPECTED_TOOLS = {
    "list_matches",
    "get_match_state",
    "get_metric",
    "compare_windows",
    "get_events",
    "get_player",
    "list_moments",
}
SERVER = create_server(demo_store())


def with_client[T](action: Callable[[ClientSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with create_connected_server_and_client_session(SERVER) as client:
            return await action(client)

    return anyio.run(run)


def call(name: str, arguments: dict[str, Any]) -> CallToolResult:
    async def send(client: ClientSession) -> CallToolResult:
        return await client.call_tool(name, arguments)

    return with_client(send)


def text_of(result: CallToolResult) -> str:
    return " ".join(c.text for c in result.content if isinstance(c, TextContent))


def test_every_tool_is_listed_read_only_with_input_and_output_schemas() -> None:
    listed = with_client(lambda client: client.list_tools())

    assert {t.name for t in listed.tools} == EXPECTED_TOOLS
    for tool in listed.tools:
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.openWorldHint is False
        assert tool.description
        assert tool.inputSchema["type"] == "object"
        assert tool.outputSchema is not None
        assert tool.outputSchema.get("properties"), tool.name


def test_a_tool_call_returns_structured_camel_case_content() -> None:
    result = call("get_match_state", {"match_id": "m42"})

    assert not result.isError
    content: dict[str, Any] = result.structuredContent or {}
    assert content["matchId"] == "m42"
    assert content["score"] == {"home": 2, "away": 1}


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("get_match_state", {"match_id": "m99"}),
        ("get_match_state", {"match_id": "'; DROP TABLE SECRET"}),
        (
            "get_metric",
            {"match_id": "m42", "metric": "SECRET_metric", "scope": "HCY", "window": "5m"},
        ),
        (
            "get_metric",
            {"match_id": "m42", "metric": "xg", "scope": "SECRET<script>", "window": "5m"},
        ),
        ("get_metric", {"match_id": "m42", "metric": "xg", "scope": "SLT", "window": "5m"}),
        ("get_match_state", {"match_id": "m42", "as_of_seq": "SECRET"}),
        ("get_match_state", {"match_id": "m42", "as_of_seq": True}),
        ("get_match_state", {"match_id": "m42", "extra": "SECRET"}),
        ("get_events", {"match_id": "m42", "from_seq": 0, "to_seq": 10}),
        ("get_player", {"match_id": "m42", "player_id": "KBA-01"}),
    ],
)
def test_bad_arguments_are_errors_that_never_repeat_their_values(
    name: str, arguments: dict[str, Any]
) -> None:
    result = call(name, arguments)

    assert result.isError
    assert "SECRET" not in text_of(result)
    assert "DROP" not in text_of(result)


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


def test_http_answers_only_to_loopback_and_the_listed_public_host() -> None:
    server = create_server(demo_store(), host="0.0.0.0", allowed_hosts=["data.example.net"])  # noqa: S104 - container bind

    security = server.settings.transport_security
    assert security is not None
    assert security.enable_dns_rebinding_protection
    assert security.allowed_hosts == [*LOOPBACK, "data.example.net"]
    assert security.allowed_origins == []


def test_the_command_line_serves_stdio_or_http(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[tuple[str, str, int, list[str]]] = []

    def fake_run(self: FastMCP, transport: str) -> None:
        security = self.settings.transport_security
        hosts = list(security.allowed_hosts) if security else []
        served.append((transport, self.settings.host, self.settings.port, hosts))

    monkeypatch.setattr(FastMCP, "run", fake_run)
    entry.main([])
    entry.main(["--http", "--host", "0.0.0.0", "--port", "8123", "--allowed-host", "x.example"])  # noqa: S104

    assert served[0][:3] == ("stdio", "127.0.0.1", 8100)
    assert served[1][:3] == ("streamable-http", "0.0.0.0", 8123)  # noqa: S104
    assert served[1][3] == [*LOOPBACK, "x.example"]
