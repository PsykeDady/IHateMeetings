from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoiceRegion:
    start: float
    end: float


@dataclass(frozen=True)
class VoiceEmbedding:
    model: str
    values: tuple[float, ...]


class VoiceEmbeddingBackend(ABC):
    """Future local embedding boundary; Phase 4 ships no unvalidated implementation."""

    @abstractmethod
    def embed(self, audio_path: Path, regions: tuple[VoiceRegion, ...]) -> VoiceEmbedding:
        """Extract an embedding from explicitly selected, single-speaker regions."""


def speaker_data_dir() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    root = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return root / "ihatemeetings" / "speakers"


def ensure_private_speaker_data_dir(path: Path | None = None) -> Path:
    target = path or speaker_data_dir()
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.chmod(0o700)
    return target
