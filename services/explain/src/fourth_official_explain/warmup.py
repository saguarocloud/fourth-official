"""Waking a model deployment before it is needed. The first call to a deployment after a quiet
spell can take as long as the pipeline's timeout (seen in the traces, ADR-017), so the first
moment of every match would wait for it; one tiny request as a run kicks off pays that instead.
It costs a few dozen tokens and is not counted against any match.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast

from agent_framework import ChatOptions, Message

# Longer than a cold start, short enough not to linger after the run has moved on.
WARM_TIMEOUT_SECONDS = 30.0
# The reply needs a word; reasoning models count their thinking against the limit too.
MAX_TOKENS = 64

Warm = Callable[[], Awaitable[None]]


# A chat client's `get_response`: the agent's own client, so the warm connection is the one used.
Send = Callable[..., Awaitable[object]]


def warm_up(send: Send, *, options: Mapping[str, object]) -> Warm:
    """One short request through `send`, with the deployment's own options, bounded."""

    async def warm() -> None:
        request = cast("ChatOptions[Any]", {**options, "max_tokens": MAX_TOKENS})
        async with asyncio.timeout(WARM_TIMEOUT_SECONDS):
            await send([Message("user", ["Reply with OK."])], options=request)

    return warm
