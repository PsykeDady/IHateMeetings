from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime options after applying the initial precedence rules."""

    profile: str | None = None
    language: str | None = None
    config_file: Path | None = None

    @classmethod
    def from_sources(
        cls,
        *,
        profile: str | None = None,
        language: str | None = None,
        config_file: Path | None = None,
    ) -> "RuntimeConfig":
        return cls(
            profile=profile or os.environ.get("IHM_PROFILE"),
            language=language or os.environ.get("IHM_LANGUAGE"),
            config_file=config_file,
        )

