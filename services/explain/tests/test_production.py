"""The production configuration: one definition the API runs and the Proving Ground gates."""

from fourth_official_explain.metering import TokenCount
from fourth_official_explain.production import ANALYST, LOCALIZER, MODELS, analyst_drafters
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
