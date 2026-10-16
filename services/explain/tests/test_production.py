"""The production configuration: one definition the API runs and the Proving Ground gates."""

from fourth_official_explain.metering import TokenCount
from fourth_official_explain.production import (
    ANALYST,
    LOCALIZER,
    MODELS,
    PRICES,
    Price,
    analyst_drafters,
    micro_dollars,
)
from test_analyst import NoNetworkCredential

ENDPOINT = "https://example.services.ai.azure.com/api/projects/demo"
MCP = "http://127.0.0.1:8100/mcp"


def test_production_drafts_with_the_fast_model_then_the_fallback() -> None:
    drafters = analyst_drafters(
        project_endpoint=ENDPOINT, match_data_url=MCP, credential=NoNetworkCredential()
    )

    assert ANALYST == ("analyst", "v1.2")
    assert LOCALIZER == ("localizer", "v1.0")
    assert [d.provenance.model for d in drafters] == [alias for alias, _ in MODELS]
    assert [d.provenance.prompt_version for d in drafters] == ["v1.2", "v1.2"]
    assert drafters[0].options == {"reasoning": {"effort": "minimal"}}
    assert drafters[1].options == {}


def test_another_prompt_version_can_be_drafted_with_and_metered() -> None:
    spent: list[TokenCount] = []
    drafters = analyst_drafters(
        project_endpoint=ENDPOINT,
        match_data_url=MCP,
        credential=NoNetworkCredential(),
        prompt=("analyst", "v1.0"),
        meter=spent.append,
    )

    assert {d.provenance.prompt_version for d in drafters} == {"v1.0"}
    assert all(d.meter == spent.append for d in drafters)


def test_every_production_model_has_a_list_price_in_micro_dollars() -> None:
    assert {alias for alias, _ in MODELS} <= set(PRICES)
    assert PRICES["fast"] == Price(
        input_microusd_per_million=250_000, output_microusd_per_million=2_000_000
    )
    assert PRICES["fallback"] == Price(
        input_microusd_per_million=400_000, output_microusd_per_million=1_600_000
    )


def test_tokens_are_priced_in_whole_micro_dollars_rounded_once() -> None:
    spent = [
        TokenCount(model="fast", input=1_000_000, output=100_000),
        TokenCount(model="fallback", input=1, output=1),
    ]

    # 250 000 + 200 000 for fast, and 0.4 + 1.6 = 2 for the single fallback tokens.
    assert micro_dollars(spent) == 450_002
    assert micro_dollars([TokenCount(model="fast", input=1, output=0)]) == 0
    assert micro_dollars([TokenCount(model="fast", input=2, output=0)]) == 1
