from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime options after applying the initial precedence rules."""

    profile: str | None = None
    language: str | None = None
    model: str | None = None
    device: str = "auto"
    compute_type: str | None = None
    output_dir: Path = Path("output")
    config_file: Path | None = None

    @classmethod
    def from_sources(
        cls,
        *,
        profile: str | None = None,
        language: str | None = None,
        model: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        output_dir: Path | None = None,
        config_file: Path | None = None,
    ) -> RuntimeConfig:
        return cls(
            profile=profile or os.environ.get("IHM_PROFILE"),
            language=language or os.environ.get("IHM_LANGUAGE"),
            model=model or os.environ.get("IHM_MODEL"),
            device=device or os.environ.get("IHM_DEVICE", "auto"),
            compute_type=compute_type or os.environ.get("IHM_COMPUTE_TYPE"),
            output_dir=output_dir or Path(os.environ.get("IHM_OUTPUT_DIR", "output")),
            config_file=config_file,
        )
