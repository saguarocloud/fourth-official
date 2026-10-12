"""Export the contracts as JSON Schema (2020-12) for language-neutral consumers.

The Pydantic models are the source of truth; `packages/contracts/schemas/*.schema.json` are
generated from them and checked for drift by the test suite. TypeScript types will be generated
from those files when the web app consumes events. Regenerate with `make contracts`.
"""

import json
from pathlib import Path
from typing import Any

from fourth_official_contracts.corrections import CORRECTION_ADAPTER
from fourth_official_contracts.events import MATCH_EVENT_ADAPTER
from fourth_official_contracts.feed import FEED_ENTRY_ADAPTER
from fourth_official_contracts.ground_truth import GROUND_TRUTH_ADAPTER
from fourth_official_contracts.insights import INSIGHT_ADAPTER
from fourth_official_contracts.localized import LOCALIZED_INSIGHT_ADAPTER
from fourth_official_contracts.metrics import METRIC_SNAPSHOT_ADAPTER
from fourth_official_contracts.moments import MOMENT_ADAPTER
from fourth_official_contracts.overlays import OVERLAY_SPEC_ADAPTER
from fourth_official_contracts.policy_history import POLICY_HISTORY_ADAPTER
from fourth_official_contracts.provenance import SIGNED_PROVENANCE_ADAPTER
from fourth_official_contracts.scorecard import GATE_VERDICT_ADAPTER, SCORECARD_ADAPTER
from fourth_official_contracts.tenants import TENANT_POLICY_ADAPTER
from fourth_official_contracts.verdicts import VERDICT_ADAPTER

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
SCHEMA_ID_BASE = "https://github.com/saguarocloud/fourth-official/schemas/"


def _with_header(schema: dict[str, Any], name: str, title: str) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{SCHEMA_ID_BASE}{name}",
        "title": title,
        **schema,
    }


def export_schemas() -> dict[str, dict[str, Any]]:
    """Every contract's JSON Schema, keyed by file name, in wire (camelCase) form."""
    return {
        "match-event.schema.json": _with_header(
            MATCH_EVENT_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "match-event.schema.json",
            "MatchEvent",
        ),
        "metric-snapshot.schema.json": _with_header(
            METRIC_SNAPSHOT_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "metric-snapshot.schema.json",
            "MetricSnapshot",
        ),
        "correction.schema.json": _with_header(
            CORRECTION_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "correction.schema.json",
            "Correction",
        ),
        "feed-entry.schema.json": _with_header(
            FEED_ENTRY_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "feed-entry.schema.json",
            "FeedEntry",
        ),
        "ground-truth.schema.json": _with_header(
            GROUND_TRUTH_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "ground-truth.schema.json",
            "GroundTruth",
        ),
        "insight.schema.json": _with_header(
            INSIGHT_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "insight.schema.json",
            "Insight",
        ),
        "moment.schema.json": _with_header(
            MOMENT_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "moment.schema.json",
            "Moment",
        ),
        "localized-insight.schema.json": _with_header(
            LOCALIZED_INSIGHT_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "localized-insight.schema.json",
            "LocalizedInsight",
        ),
        "overlay-spec.schema.json": _with_header(
            OVERLAY_SPEC_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "overlay-spec.schema.json",
            "OverlaySpec",
        ),
        "policy-history.schema.json": _with_header(
            POLICY_HISTORY_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "policy-history.schema.json",
            "PolicyHistory",
        ),
        "scorecard.schema.json": _with_header(
            SCORECARD_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "scorecard.schema.json",
            "Scorecard",
        ),
        "gate-verdict.schema.json": _with_header(
            GATE_VERDICT_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "gate-verdict.schema.json",
            "GateVerdict",
        ),
        "signed-provenance.schema.json": _with_header(
            SIGNED_PROVENANCE_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "signed-provenance.schema.json",
            "SignedProvenance",
        ),
        "tenant-policy.schema.json": _with_header(
            TENANT_POLICY_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "tenant-policy.schema.json",
            "TenantPolicy",
        ),
        "verdict.schema.json": _with_header(
            VERDICT_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "verdict.schema.json",
            "Verdict",
        ),
    }


def write_schemas(directory: Path = SCHEMA_DIR) -> list[Path]:
    """Write every schema as stable, pretty-printed JSON; returns the files written."""
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, schema in export_schemas().items():
        path = directory / name
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        written.append(path)
    return written


if __name__ == "__main__":
    for path in write_schemas():
        print(f"wrote {path}")
