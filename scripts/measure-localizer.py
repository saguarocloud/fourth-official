"""Measure the Localizer on the demo matchday: how often each partner's version passes.

Localises every demo moment's canonical insight (the English template, so no Analyst cost) for
each non-English partner, with the real Localizer on Foundry, exactly as the replay will. Prints
first-attempt passes, model-written versions, template fallbacks, model attempts and the finding
codes that refused drafts; the JSON report keeps every draft and the findings each retry was given.

It spends model tokens: about 35 to 70 small calls. Needs the developer's Azure sign-in:

    FOUNDRY_PROJECT_ENDPOINT=$(azd env get-value FOUNDRY_PROJECT_ENDPOINT) \\
        uv run python scripts/measure-localizer.py localizer-report.json
"""

import asyncio
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from azure.identity.aio import DefaultAzureCredential

from fourth_official_contracts import Provenance
from fourth_official_explain.localize import (
    LocalizationRequest,
    LocalizedDraft,
    localize,
)
from fourth_official_explain.localizer import AgentLocalizer, foundry_localizer
from fourth_official_explain.prompts import load_prompt
from fourth_official_match_data import demo_store
from fourth_official_policy import blocked_topics_in, bundled_store
from fourth_official_replay import facts_for
from fourth_official_verifier import template_insight

PARTNERS = ("tribuna-austral", "rheinblick-sport")


@dataclass
class Recorder:
    """Passes each request to the real localizer and keeps what it was told and what it wrote."""

    inner: AgentLocalizer
    log: list[dict[str, Any]] = field(default_factory=list)

    @property
    def provenance(self) -> Provenance:
        return self.inner.provenance

    async def draft(self, request: LocalizationRequest) -> LocalizedDraft:
        entry: dict[str, Any] = {
            "insight": request.canonical.insight_id,
            "tenant": request.policy.tenant_id,
            "attempt": request.attempt,
            "feedback": [f"{f.code}: {f.detail}" for f in request.feedback],
        }
        self.log.append(entry)
        draft = await self.inner.draft(request)
        entry["draft"] = draft.model_dump(mode="json")
        return draft


async def measure(endpoint: str) -> dict[str, Any]:
    store, policies = demo_store(), bundled_store()
    results: list[dict[str, Any]] = []
    async with DefaultAzureCredential() as credential:
        localizer = Recorder(
            foundry_localizer(
                project_endpoint=endpoint,
                deployment="fast",
                alias="fast",
                prompt=load_prompt("localizer", "v1.0"),
                credential=credential,
                reasoning_effort="minimal",
            )
        )
        for match_id in store.match_ids():
            record = store.record(match_id)
            facts = facts_for(record)
            for moment in record.moments:
                canonical = template_insight(moment, facts)
                for tenant in PARTNERS:
                    policy = policies.get(tenant).policy  # type: ignore[arg-type]
                    result = await localize(
                        canonical,
                        moment,
                        facts,
                        policy,
                        localizer=localizer,
                        blocked=partial(blocked_topics_in, policy=policy),
                    )
                    results.append(
                        {
                            "tenant": tenant,
                            "moment": moment.moment_id,
                            "attempts": [
                                {
                                    "model": a.model,
                                    "outcome": a.outcome,
                                    "findings": list(a.findings),
                                }
                                for a in result.attempts
                            ],
                        }
                    )
    return {"summary": summarise(results), "results": results, "drafts": localizer.log}


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for tenant in PARTNERS:
        mine = [r for r in results if r["tenant"] == tenant]
        model = [[a for a in r["attempts"] if a["model"] != "none"] for r in mine]
        summary[tenant] = {
            "moments": len(mine),
            "first_attempt_pass": sum(1 for r in mine if r["attempts"][0]["outcome"] == "passed"),
            "model_written": sum(1 for r in mine if r["attempts"][-1]["model"] != "none"),
            "template": sum(1 for r in mine if r["attempts"][-1]["model"] == "none"),
            "model_attempts": sum(len(a) for a in model),
            "codes": Counter(c for attempts in model for a in attempts for c in a["findings"]),
        }
    return summary


def main() -> None:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not endpoint:
        raise SystemExit(
            "set FOUNDRY_PROJECT_ENDPOINT (azd env get-value FOUNDRY_PROJECT_ENDPOINT)"
        )
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "localizer-report.json")
    report = asyncio.run(measure(endpoint))
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=1))


if __name__ == "__main__":
    main()
