"""The committed JSON Schemas are exactly what the models export: no drift, ever."""

import json
from pathlib import Path

import pytest

from fourth_official_contracts.schema import SCHEMA_DIR, export_schemas, write_schemas


@pytest.mark.parametrize(("name", "schema"), sorted(export_schemas().items()))
def test_committed_schema_matches_the_models(name: str, schema: dict[str, object]) -> None:
    committed = json.loads((SCHEMA_DIR / name).read_text())

    assert committed == schema, f"{name} is stale: run `make contracts`"


def test_no_stale_schema_files_are_left_behind() -> None:
    assert {p.name for p in SCHEMA_DIR.glob("*.schema.json")} == set(export_schemas())


def test_write_schemas_produces_stable_pretty_json(tmp_path: Path) -> None:
    written = write_schemas(tmp_path)

    assert sorted(p.name for p in written) == sorted(export_schemas())
    for path in written:
        text = path.read_text()
        assert text.endswith("}\n")
        assert json.loads(text) == export_schemas()[path.name]
