"""The Match Data MCP server: the tools agents use to read a match, over the MCP protocol.

Every tool is read-only and closed-world: it answers from the match store, never from the web.
Arguments are validated by their schemas before a tool runs; errors name the problem without
echoing the input.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from fourth_official_contracts import MetricName, MetricWindow
from fourth_official_match_data import tools
from fourth_official_match_data.store import MatchDataError, MatchStore

INSTRUCTIONS = (
    "Read-only facts about Meridian League matches, bounded by what has been published so far. "
    "Numbers come from the stats engine; quote them by snapshot ID, never recompute them."
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

MatchId = Annotated[str, Field(pattern=r"^m[0-9]{1,12}$", description="Match ID, e.g. m42")]
Scope = Annotated[str, Field(pattern=r"^([A-Z]{3}|match)$", description="Club code or 'match'")]
AsOfSeq = Annotated[
    int | None,
    Field(ge=1, le=1_000_000, description="Event seq to read at; defaults to the live position"),
]
EventType = Annotated[str, Field(pattern=r"^[A-Z_]{3,20}$")]


@contextmanager
def _as_tool_errors() -> Iterator[None]:
    """Refusals from the store become tool errors the caller sees; nothing else leaks."""
    try:
        yield
    except MatchDataError as refused:
        raise ToolError(str(refused)) from None


def create_server(store: MatchStore) -> FastMCP:
    server = FastMCP("fourth-official-match-data", instructions=INSTRUCTIONS)

    @server.tool(annotations=READ_ONLY)
    def list_matches() -> dict[str, Any]:
        """Matches on the matchday, with their clubs and how far each has been published."""
        with _as_tool_errors():
            return {"matches": tools.list_matches(store)}

    @server.tool(annotations=READ_ONLY)
    def get_match_state(match_id: MatchId, as_of_seq: AsOfSeq = None) -> dict[str, Any]:
        """Score (without voided goals), clock and clubs at a moment of the match."""
        with _as_tool_errors():
            return tools.get_match_state(store, match_id, as_of_seq=as_of_seq)

    @server.tool(annotations=READ_ONLY)
    def get_metric(  # noqa: PLR0917 - MCP passes tool arguments by name
        match_id: MatchId,
        metric: MetricName,
        scope: Scope,
        window: MetricWindow,
        as_of_seq: AsOfSeq = None,
    ) -> dict[str, Any]:
        """A metric snapshot: value, window, moment and the exact events it was computed from."""
        with _as_tool_errors():
            return tools.get_metric(
                store, match_id, metric=metric, scope=scope, window=window, as_of_seq=as_of_seq
            )

    @server.tool(annotations=READ_ONLY)
    def compare_windows(
        match_id: MatchId, metric: MetricName, scope: Scope, as_of_seq: AsOfSeq = None
    ) -> dict[str, Any]:
        """The metric over the last five minutes and over the fifteen minutes before them."""
        with _as_tool_errors():
            return tools.compare_windows(
                store, match_id, metric=metric, scope=scope, as_of_seq=as_of_seq
            )

    @server.tool(annotations=READ_ONLY)
    def get_events(
        match_id: MatchId,
        from_seq: Annotated[int, Field(ge=1, le=1_000_000)],
        to_seq: Annotated[int, Field(ge=1, le=1_000_000)],
        types: Annotated[list[EventType] | None, Field(max_length=19)] = None,
    ) -> dict[str, Any]:
        """Published events in a seq range (at most 100), optionally only some event types."""
        with _as_tool_errors():
            events = tools.get_events(
                store, match_id, from_seq=from_seq, to_seq=to_seq, types=types
            )
        return {"events": events}

    @server.tool(annotations=READ_ONLY)
    def get_player(
        match_id: MatchId, player_id: Annotated[str, Field(pattern=r"^[A-Z]{3}-[0-9]{2}$")]
    ) -> dict[str, Any]:
        """A player's name, club, shirt number and position."""
        with _as_tool_errors():
            return tools.get_player(store, match_id, player_id=player_id)

    @server.tool(annotations=READ_ONLY)
    def list_moments(match_id: MatchId, as_of_seq: AsOfSeq = None) -> dict[str, Any]:
        """Moments the detector has found so far, each with its evidence."""
        with _as_tool_errors():
            return {"moments": tools.list_moments(store, match_id, as_of_seq=as_of_seq)}

    return server
