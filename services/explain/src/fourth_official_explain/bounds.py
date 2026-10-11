"""Keep every tool call inside the moment being explained.

The Match Data tools are bounded by what has been published, which during a replay or a retry is
later than the moment. This function middleware rewrites each call's arguments before it runs, so
the agent cannot read past the moment whatever it asks for.
"""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from agent_framework import FunctionInvocationContext, FunctionMiddleware
from pydantic import BaseModel

# Tools that read the match at a point in it; the others (get_player) are timeless.
AT_A_POINT = frozenset({"get_match_state", "get_metric", "compare_windows", "list_moments"})


def bounded_arguments(name: str, arguments: Mapping[str, Any], as_of_seq: int) -> dict[str, Any]:
    """The arguments of a Match Data call, clamped to `as_of_seq`."""
    bounded = dict(arguments)
    if name == "get_events":
        to_seq = min(int(bounded.get("to_seq", as_of_seq)), as_of_seq)
        bounded["to_seq"] = to_seq
        bounded["from_seq"] = min(int(bounded.get("from_seq", 1)), to_seq)
    elif name in AT_A_POINT:
        asked = bounded.get("as_of_seq")
        bounded["as_of_seq"] = as_of_seq if asked is None else min(int(asked), as_of_seq)
    return bounded


class MomentBound(FunctionMiddleware):
    """Clamps every tool call of one agent run to the moment's `as_of_seq`."""

    def __init__(self, as_of_seq: int) -> None:
        self.as_of_seq = as_of_seq

    async def process(
        self, context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]
    ) -> None:
        raw = context.arguments
        arguments = raw.model_dump() if isinstance(raw, BaseModel) else dict(raw)
        context.arguments = bounded_arguments(context.function.name, arguments, self.as_of_seq)
        await call_next()
