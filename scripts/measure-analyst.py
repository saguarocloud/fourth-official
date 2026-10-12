"""Measure the Analyst on the demo matchday: how often each moment passes the Verifier.

Runs the real Analyst (Foundry models, the Match Data MCP server) over each match's moments, the
same way the API does, and prints first-attempt passes, insights the model wrote, template
fallbacks, model attempts and the finding codes that refused drafts. The JSON report also keeps
every draft, with the findings (and their detail) each retry was given.

It spends model tokens: about 20-70 model calls for the whole matchday. Needs the developer's
Azure sign-in (Azure AI User on the Foundry account) and the MCP server running locally:

    uv run python -m fourth_official_match_data --http &
    FOUNDRY_PROJECT_ENDPOINT=$(azd env get-value FOUNDRY_PROJECT_ENDPOINT) \\
        uv run python scripts/measure-analyst.py m42,m43,m44 analyst-report.json
"""

import asyncio
import json
import os
import sys
from collections import Counter
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from azure.identity.aio import DefaultAzureCredential

from fourth_official_api.explainers import foundry_drafters
from fourth_official_api.settings import FoundrySettings
from fourth_official_contracts import Moment, Provenance
from fourth_official_explain import Explanation, explain
from fourth_official_explain.analyst import AgentDrafter
from fourth_official_explain.drafts import InsightDraft
from fourth_official_explain.pipeline import DraftRequest
from fourth_official_explain.production import ANALYST
from fourth_official_match_data import demo_store
from fourth_official_replay import FeedLog, replay
from fourth_official_verifier import MatchFacts

MATCH_DATA_URL = "http://127.0.0.1:8100/mcp"


@dataclass
class Recorder:
    """Passes each request to the real drafter and keeps what it was told and what it wrote."""

    inner: AgentDrafter
    log: list[dict[str, Any]] = field(default_factory=list)

    @property
    def provenance(self) -> Provenance:
        return self.inner.provenance

    async def draft(self, request: DraftRequest) -> InsightDraft:
        entry: dict[str, Any] = {
            "moment": request.moment.moment_id,
            "attempt": request.attempt,
            "model": self.inner.provenance.model,
            "feedback": [f"{f.code}: {f.detail}" for f in request.feedback],
        }
        self.log.append(entry)
        draft = await self.inner.draft(request)
        entry["draft"] = draft.model_dump(mode="json")
        return draft


async def no_wait(seconds: float) -> None:
    return None


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_model = [[a for a in r["attempts"] if a["model"] != "none"] for r in results]
    return {
        "prompt": "/".join(ANALYST),
        "moments": len(results),
        "first_attempt_pass": sum(1 for r in results if r["attempts"][0]["outcome"] == "passed"),
        "model_written": sum(1 for r in results if r["attempts"][-1]["model"] != "none"),
        "template": sum(1 for r in results if r["attempts"][-1]["model"] == "none"),
        "model_attempts": sum(len(a) for a in by_model),
        "codes": Counter(c for attempts in by_model for a in attempts for c in a["findings"]),
    }


async def measure(matches: list[str]) -> dict[str, Any]:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not endpoint:
        raise SystemExit(
            "set FOUNDRY_PROJECT_ENDPOINT (azd env get-value FOUNDRY_PROJECT_ENDPOINT)"
        )
    settings = FoundrySettings(
        project_endpoint=endpoint,
        match_data_url=MATCH_DATA_URL,
        client_id="",
    )
    results: list[dict[str, Any]] = []
    async with AsyncExitStack() as stack:
        credential = await stack.enter_async_context(DefaultAzureCredential())
        drafters = [
            Recorder(await stack.enter_async_context(d))
            for d in foundry_drafters(settings, credential)
        ]

        async def explainer(moment: Moment, facts: MatchFacts) -> Explanation:
            explained = await explain(moment, facts, drafters)
            results.append(
                {
                    "moment": moment.moment_id,
                    "attempts": [
                        {
                            "model": a.model,
                            "outcome": a.outcome,
                            "findings": list(a.findings),
                            "error": a.error,
                        }
                        for a in explained.attempts
                    ],
                }
            )
            return explained

        for match_id in matches:
            await replay(demo_store().record(match_id), FeedLog(match_id), explainer, sleep=no_wait)
    return {
        "summary": summarise(results),
        "results": results,
        "drafts": [entry for d in drafters for entry in d.log],
    }


def main() -> None:
    matches = (sys.argv[1] if len(sys.argv) > 1 else "m42,m43,m44").split(",")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "analyst-report.json")
    report = asyncio.run(measure(matches))
    out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=1))


if __name__ == "__main__":
    main()
