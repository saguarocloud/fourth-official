"""Runtime settings, read once from the environment at startup."""

import os
from dataclasses import dataclass

DEFAULT_VERSION = "dev"


@dataclass(frozen=True, slots=True)
class Settings:
    version: str

    @classmethod
    def from_env(cls) -> "Settings":
        # APP_VERSION is the git SHA injected by the deploy pipeline.
        version = os.environ.get("APP_VERSION", "").strip()
        return cls(version=version or DEFAULT_VERSION)
