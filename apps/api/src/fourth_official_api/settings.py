"""Runtime settings, read once from the environment at startup."""

import os
from dataclasses import dataclass

DEFAULT_VERSION = "dev"


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable runtime configuration for the API."""

    version: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Read settings from environment variables, applying defaults for unset values."""
        # APP_VERSION is the git SHA injected by the deploy pipeline.
        version = os.environ.get("APP_VERSION", "").strip()
        return cls(version=version or DEFAULT_VERSION)
