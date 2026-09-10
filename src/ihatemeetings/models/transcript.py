from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MediaInfo:
    source: Path
    duration: float
    format_name: str
    size_bytes: int | None
    start_time: float | None
    audio_streams: int
    video_streams: int

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = str(self.source)
        return data


@dataclass(frozen=True)
class ASRSegment:
    start: float
    end: float
    text: str
    token_ids: tuple[int, ...] = field(default_factory=tuple)
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    compression_ratio: float | None = None
    temperature: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "token_ids": list(self.token_ids)}


@dataclass(frozen=True)
class ASRResult:
    backend: str
    backend_version: str
    model: str
    language: str | None
    language_probability: float | None
    duration: float
    duration_after_vad: float | None
    segments: tuple[ASRSegment, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "segments": [segment.to_dict() for segment in self.segments],
        }


@dataclass(frozen=True)
class TranscriptSegment:
    id: str
    start: float
    end: float
    text: str
    speaker: None = None
    confidence: None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Transcript:
    duration: float
    language: str | None
    language_probability: float | None
    source: str
    segments: tuple[TranscriptSegment, ...] = field(default_factory=tuple)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "meeting": {
                "source": self.source,
                "duration": self.duration,
                "language": self.language,
                "language_probability": self.language_probability,
            },
            "speakers": [],
            "segments": [segment.to_dict() for segment in self.segments],
        }
