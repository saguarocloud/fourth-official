"""What each model call spends, collected for the attempt that made it.

An agent reports the tokens of every call it makes with `spend`. The pipeline collects them
around each attempt (`collecting`), so the attempt records what it cost wherever it ran. The
collector is a context variable: concurrent moments each collect their own, and a call made
outside any attempt is reported nowhere.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenCount:
    """Tokens one model call spent, under the model's configured alias."""

    model: str
    input: int
    output: int


def usage_of(response: object, model: str) -> TokenCount | None:
    """The tokens an Agent Framework response reports, if it reports them."""
    usage = getattr(response, "usage_details", None)
    if not isinstance(usage, Mapping):
        return None
    tokens_in, tokens_out = usage.get("input_token_count"), usage.get("output_token_count")
    if not isinstance(tokens_in, int) or not isinstance(tokens_out, int):
        return None
    return TokenCount(model=model, input=tokens_in, output=tokens_out)


_collector: ContextVar[list[TokenCount] | None] = ContextVar("tokens", default=None)


def spend(count: TokenCount) -> None:
    """Report a call's tokens to the attempt collecting them, if any."""
    collected = _collector.get()
    if collected is not None:
        collected.append(count)


@contextmanager
def collecting() -> Iterator[list[TokenCount]]:
    """Collect the tokens spent within the block, in the order they were spent."""
    spent: list[TokenCount] = []
    token = _collector.set(spent)
    try:
        yield spent
    finally:
        _collector.reset(token)


def totals(spent: list[TokenCount]) -> tuple[int, int]:
    """Input and output tokens spent in all."""
    return sum(c.input for c in spent), sum(c.output for c in spent)
