from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DiarizationOptions:
    model_path: Path
    model_name: str
    device: str
    num_speakers: int | None = None
    min_speakers: int | None = None
    max_speakers: int | None = None


@dataclass(frozen=True)
class DiarizationParameters:
    device: str | None = None
    num_speakers: int | None = None
    min_speakers: int | None = None
    max_speakers: int | None = None

    def to_dict(self) -> dict[str, str | int | None]:
        return asdict(self)


@dataclass(frozen=True)
class DiarizationTurn:
    speaker_id: str
    start: float
    end: float
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not self.speaker_id:
            raise ValueError("speaker_id cannot be empty")
        if self.start < 0 or self.end < self.start:
            raise ValueError("diarization timestamps must be ordered and non-negative")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("diarization confidence must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiarizationResult:
    backend: str
    backend_version: str
    model: str | None
    status: str
    turns: tuple[DiarizationTurn, ...] = ()
    warnings: tuple[str, ...] = ()
    parameters: DiarizationParameters | None = None

    def __post_init__(self) -> None:
        if any(
            current.start > following.start
            for current, following in zip(self.turns, self.turns[1:])
        ):
            raise ValueError("diarization turns must be ordered by start time")

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "backend_version": self.backend_version,
            "model": self.model,
            "status": self.status,
            "turns": [turn.to_dict() for turn in self.turns],
            "warnings": list(self.warnings),
            "parameters": self.parameters.to_dict() if self.parameters else {},
        }


class DiarizationBackend(ABC):
    @abstractmethod
    def diarize(self, audio_path: Path, options: DiarizationOptions) -> DiarizationResult:
        """Return speaker clusters without attempting speaker identification."""
