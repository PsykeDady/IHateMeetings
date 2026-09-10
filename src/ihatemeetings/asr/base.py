from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ihatemeetings.models import ASRResult


@dataclass(frozen=True)
class ASROptions:
    model_path: Path
    model_name: str
    language: str | None
    device: str
    compute_type: str
    glossary_terms: tuple[str, ...] = ()


class ASRBackend(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path, options: ASROptions) -> ASRResult:
        """Transcribe normalized audio into IHateMeetings models."""
