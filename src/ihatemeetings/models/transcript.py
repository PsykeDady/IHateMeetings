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
    words: tuple[Word, ...] = field(default_factory=tuple)
    speaker: None = None
    confidence: None = None

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "words": [word.to_dict() for word in self.words]}


@dataclass(frozen=True)
class Word:
    text: str
    start: float | None
    end: float | None
    confidence: float | None

    def __post_init__(self) -> None:
        if (self.start is None) != (self.end is None):
            raise ValueError("word start and end must both be present or absent")
        if (
            self.start is not None
            and self.end is not None
            and (self.start < 0 or self.end < self.start)
        ):
            raise ValueError("word timestamps must be ordered and non-negative")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("word confidence must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Transcript:
    duration: float
    language: str | None
    language_probability: float | None
    source: str
    segments: tuple[TranscriptSegment, ...] = field(default_factory=tuple)
    schema_version: int = 2

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
