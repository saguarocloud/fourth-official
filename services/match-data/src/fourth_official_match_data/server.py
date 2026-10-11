"""The Match Data MCP server: the tools agents use to read a match, over the MCP protocol.

Every tool is read-only and closed-world: it answers from the match store, never from the web.
Arguments are validated strictly against their schemas (unknown arguments refused) before a tool
runs. Errors may name the argument at fault but never repeat a value the caller sent. Every tool
declares its output schema.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

from fourth_official_contracts import MetricName, MetricSnapshot, MetricWindow
from fourth_official_match_data import tools
from fourth_official_match_data.models import (
    EventPage,
    MatchList,
    MatchState,
    MomentList,
    PlayerInfo,
    WindowComparison,
)
from fourth_official_match_data.store import MatchDataError, MatchStore

INSTRUCTIONS = (
    "Read-only facts about Meridian League matches, bounded by what has been published so far. "
    "Numbers come from the stats engine; quote them by snapshot ID, never recompute them."
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
LOOPBACK = ("127.0.0.1:*", "localhost:*", "[::1]:*")

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


def _harden_arguments(server: FastMCP) -> None:
    """Validate every tool's arguments strictly, refuse unknown ones, and never echo values."""
    for tool in server._tool_manager.list_tools():
        model = tool.fn_metadata.arg_model
        model.model_config["hide_input_in_errors"] = True
        model.model_config["extra"] = "forbid"
        model.model_config["strict"] = True
        model.model_rebuild(force=True)


def create_server(
    store: MatchStore,
    *,
    host: str = "127.0.0.1",
    port: int = 8100,
    allowed_hosts: Sequence[str] = (),
) -> FastMCP:
    """The server over `store`. Over HTTP it answers only to loopback and `allowed_hosts` (the
    public host names it is served under), which guards against DNS rebinding."""
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[*LOOPBACK, *allowed_hosts],
        allowed_origins=[],
    )
    server = FastMCP(
        "fourth-official-match-data",
        instructions=INSTRUCTIONS,
        host=host,
        port=port,
        transport_security=security,
    )

    @server.tool(annotations=READ_ONLY)
    def list_matches() -> MatchList:
        """Matches on the matchday, with their clubs and how far each has been published."""
        with _as_tool_errors():
            return tools.list_matches(store)

    @server.tool(annotations=READ_ONLY)
    def get_match_state(match_id: MatchId, as_of_seq: AsOfSeq = None) -> MatchState:
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
    ) -> MetricSnapshot:
        """A metric snapshot: value, window, moment and the exact events it was computed from."""
        with _as_tool_errors():
            return tools.get_metric(
                store, match_id, metric=metric, scope=scope, window=window, as_of_seq=as_of_seq
            )

    @server.tool(annotations=READ_ONLY)
    def compare_windows(
        match_id: MatchId, metric: MetricName, scope: Scope, as_of_seq: AsOfSeq = None
    ) -> WindowComparison:
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
    ) -> EventPage:
        """Published events in a seq range, a page of at most 100, and where to continue."""
        with _as_tool_errors():
            return tools.get_events(store, match_id, from_seq=from_seq, to_seq=to_seq, types=types)

    @server.tool(annotations=READ_ONLY)
    def get_player(
        match_id: MatchId, player_id: Annotated[str, Field(pattern=r"^[A-Z]{3}-[0-9]{2}$")]
    ) -> PlayerInfo:
        """A player's name, club, shirt number and position."""
        with _as_tool_errors():
            return tools.get_player(store, match_id, player_id=player_id)

    @server.tool(annotations=READ_ONLY)
    def list_moments(match_id: MatchId, as_of_seq: AsOfSeq = None) -> MomentList:
        """Moments the detector has found so far, each with its evidence."""
        with _as_tool_errors():
            return tools.list_moments(store, match_id, as_of_seq=as_of_seq)

    _harden_arguments(server)
    return server
