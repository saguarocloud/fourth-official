"""Shared fixtures for infrastructure tests."""

from pathlib import Path

import pytest
from arm import CompiledTemplate, load_template

MAIN_BICEP = Path(__file__).resolve().parents[1] / "main.bicep"


@pytest.fixture(scope="session")
def compiled() -> CompiledTemplate:
    return load_template(MAIN_BICEP)
