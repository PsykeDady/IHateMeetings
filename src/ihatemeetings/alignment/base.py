from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ihatemeetings.models import ASRSegment, Word


@dataclass(frozen=True)
class AlignmentOptions:
    model_path: Path
    model_name: str
    language: str
    device: str


@dataclass(frozen=True)
class AlignmentSegment:
    segment_index: int
    start: float
    end: float
    text: str
    words: tuple[Word, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "words": [
                {
                    "text": word.text,
                    "start": word.start,
                    "end": word.end,
                    "confidence": word.confidence,
                }
                for word in self.words
            ],
        }


@dataclass(frozen=True)
class AlignmentResult:
    backend: str
    backend_version: str
    model: str | None
    language: str | None
    status: str
    segments: tuple[AlignmentSegment, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "segments": [segment.to_dict() for segment in self.segments],
            "warnings": list(self.warnings),
        }


class AlignmentBackend(ABC):
    @abstractmethod
    def align(
        self,
        audio_path: Path,
        segments: tuple[ASRSegment, ...],
        options: AlignmentOptions,
    ) -> AlignmentResult:
        """Align ASR text to audio and return IHateMeetings word models."""
