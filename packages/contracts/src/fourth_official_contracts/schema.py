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
from fourth_official_contracts.ground_truth import GROUND_TRUTH_ADAPTER
from fourth_official_contracts.metrics import METRIC_SNAPSHOT_ADAPTER
from fourth_official_contracts.moments import MOMENT_ADAPTER

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
        "ground-truth.schema.json": _with_header(
            GROUND_TRUTH_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "ground-truth.schema.json",
            "GroundTruth",
        ),
        "moment.schema.json": _with_header(
            MOMENT_ADAPTER.json_schema(by_alias=True, mode="validation"),
            "moment.schema.json",
            "Moment",
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
