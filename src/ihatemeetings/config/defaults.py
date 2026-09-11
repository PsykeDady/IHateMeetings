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
    align: bool | None = None
    alignment_model: str | None = None
    diarize: bool | None = None
    diarization_model: str | None = None
    num_speakers: int | None = None
    min_speakers: int | None = None
    max_speakers: int | None = None
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
        align: bool | None = None,
        alignment_model: str | None = None,
        diarize: bool | None = None,
        diarization_model: str | None = None,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        output_dir: Path | None = None,
        config_file: Path | None = None,
    ) -> RuntimeConfig:
        return cls(
            profile=profile or os.environ.get("IHM_PROFILE"),
            language=language or os.environ.get("IHM_LANGUAGE"),
            model=model or os.environ.get("IHM_MODEL"),
            device=device or os.environ.get("IHM_DEVICE", "auto"),
            compute_type=compute_type or os.environ.get("IHM_COMPUTE_TYPE"),
            align=align if align is not None else _environment_bool("IHM_ALIGN"),
            alignment_model=alignment_model or os.environ.get("IHM_ALIGNMENT_MODEL"),
            diarize=diarize if diarize is not None else _environment_bool("IHM_DIARIZE"),
            diarization_model=diarization_model or os.environ.get("IHM_DIARIZATION_MODEL"),
            num_speakers=num_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
            output_dir=output_dir or Path(os.environ.get("IHM_OUTPUT_DIR", "output")),
            config_file=config_file,
        )


def _environment_bool(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None
