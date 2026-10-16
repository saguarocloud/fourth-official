"""Production: the prompts and models the live pipeline explains with. One definition, so the API
runs exactly what the Proving Ground gates (ADR-014): a pull request that changes a prompt version
or a model here is the candidate the Release Gate judges."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from azure.core.credentials_async import AsyncTokenCredential

from fourth_official_explain.analyst import AgentDrafter, Meter, foundry_analyst
from fourth_official_explain.metering import TokenCount
from fourth_official_explain.prompts import load_prompt

Effort = Literal["minimal", "low", "medium"]
PER_MILLION = 1_000_000


@dataclass(frozen=True, slots=True)
class Price:
    """What a million tokens cost, in micro-dollars (millionths of a US dollar)."""

    input_microusd_per_million: int
    output_microusd_per_million: int


# List prices of the models behind each alias (infra/main.bicep: fast is gpt-5-mini, fallback is
# gpt-4.1-mini; Global Standard, pay as you go), in docs/cost-model.md. Change them with the
# deployments.
PRICES: Mapping[str, Price] = MappingProxyType(
    {
        "fast": Price(input_microusd_per_million=250_000, output_microusd_per_million=2_000_000),
        "fallback": Price(
            input_microusd_per_million=400_000, output_microusd_per_million=1_600_000
        ),
    }
)


def micro_dollars(spent: Iterable[TokenCount], prices: Mapping[str, Price] = PRICES) -> int:
    """What the calls cost in whole micro-dollars, rounded once at the end (half up). A model
    without a price is an error, never a guess."""
    exact = 0
    for count in spent:
        price = prices[count.model]
        exact += (
            count.input * price.input_microusd_per_million
            + count.output * price.output_microusd_per_million
        )
    return (exact + PER_MILLION // 2) // PER_MILLION


ANALYST = ("analyst", "v1.2")
LOCALIZER = ("localizer", "v1.0")
# Model aliases in the order they are tried, with each one's reasoning effort.
MODELS: tuple[tuple[str, Effort | None], ...] = (
    ("fast", "minimal"),
    ("fallback", None),
)


def analyst_drafters(
    *,
    project_endpoint: str,
    match_data_url: str,
    credential: AsyncTokenCredential,
    prompt: tuple[str, str] = ANALYST,
    models: tuple[tuple[str, Effort | None], ...] = MODELS,
    meter: Meter | None = None,
) -> list[AgentDrafter]:
    """The Analyst on each model in turn. The caller owns `credential` and closes it after the
    drafters."""
    loaded = load_prompt(*prompt)
    return [
        foundry_analyst(
            project_endpoint=project_endpoint,
            deployment=alias,
            alias=alias,
            match_data_url=match_data_url,
            prompt=loaded,
            credential=credential,
            reasoning_effort=effort,
            meter=meter,
        )
        for alias, effort in models
    ]
