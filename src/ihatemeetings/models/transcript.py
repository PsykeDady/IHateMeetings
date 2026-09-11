from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from ihatemeetings.models.speaker import Speaker, SpeakerIdentity

ReviewStatus = Literal["active", "deleted", "merged"]
AssignmentKind = Literal["identity", "cluster"]


@dataclass(frozen=True)
class ReviewAssignment:
    kind: AssignmentKind
    identity: SpeakerIdentity | None = None
    cluster: str | None = None
    method: str = "explicit_user_input"

    def __post_init__(self) -> None:
        if self.kind == "identity" and (self.identity is None or self.cluster is not None):
            raise ValueError("an identity assignment requires only an identity")
        if self.kind == "cluster" and (not self.cluster or self.identity is not None):
            raise ValueError("a cluster assignment requires only a cluster")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "identity": self.identity.to_dict() if self.identity else None,
            "cluster": self.cluster,
            "method": self.method,
        }


@dataclass(frozen=True)
class SegmentReview:
    status: ReviewStatus = "active"
    accepted: bool = False
    speaker_assignment: ReviewAssignment | None = None
    merged_segment_ids: tuple[str, ...] = field(default_factory=tuple)
    merged_into: str | None = None

    def __post_init__(self) -> None:
        if self.status == "merged" and not self.merged_into:
            raise ValueError("a merged segment requires merged_into")
        if self.status != "merged" and self.merged_into is not None:
            raise ValueError("only a merged segment may set merged_into")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "accepted": self.accepted,
            "speaker_assignment": (
                self.speaker_assignment.to_dict() if self.speaker_assignment else None
            ),
            "merged_segment_ids": list(self.merged_segment_ids),
            "merged_into": self.merged_into,
        }


@dataclass(frozen=True)
class ClusterReview:
    cluster: str
    assignment: ReviewAssignment

    def __post_init__(self) -> None:
        if self.assignment.kind != "identity":
            raise ValueError("cluster-wide review supports identity assignments only")

    def to_dict(self) -> dict[str, Any]:
        return {"cluster": self.cluster, "assignment": self.assignment.to_dict()}


@dataclass(frozen=True)
class TranscriptReview:
    cluster_assignments: tuple[ClusterReview, ...] = field(default_factory=tuple)
    migrated_from_schema: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_assignments": [item.to_dict() for item in self.cluster_assignments],
            "migrated_from_schema": self.migrated_from_schema,
        }


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
class SpeakerCandidate:
    speaker_id: str
    overlap: float


@dataclass(frozen=True)
class WordSpeakerAssignment:
    speaker_id: str | None
    method: str
    overlap: float = 0.0
    word_coverage: float = 0.0
    candidates: tuple[SpeakerCandidate, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "candidates": [asdict(candidate) for candidate in self.candidates],
        }


@dataclass(frozen=True)
class Word:
    text: str
    start: float | None
    end: float | None
    confidence: float | None
    speaker: WordSpeakerAssignment | None = None

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
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "speaker": self.speaker.to_dict() if self.speaker else None,
        }


@dataclass(frozen=True)
class TranscriptSegment:
    id: str
    start: float
    end: float
    text: str
    words: tuple[Word, ...] = field(default_factory=tuple)
    speaker: Speaker | None = None
    confidence: None = None
    unknown_id: str | None = None
    review: SegmentReview = field(default_factory=SegmentReview)

    def to_dict(self) -> dict[str, Any]:
        original = {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "words": [word.to_dict() for word in self.words],
            "speaker": self.speaker.to_dict() if self.speaker else None,
            "confidence": self.confidence,
        }
        return {
            "id": self.id,
            "unknown_id": self.unknown_id,
            **original,
            "original": original,
            "review": self.review.to_dict(),
        }


@dataclass(frozen=True)
class Transcript:
    duration: float
    language: str | None
    language_probability: float | None
    source: str
    segments: tuple[TranscriptSegment, ...] = field(default_factory=tuple)
    speakers: tuple[Speaker, ...] = field(default_factory=tuple)
    schema_version: int = 5
    review: TranscriptReview = field(default_factory=TranscriptReview)

    def __post_init__(self) -> None:
        if self.schema_version != 5:
            return
        segment_numbers: list[int] = []
        unknown_numbers: list[int] = []
        for segment in self.segments:
            match = re.fullmatch(r"SEG_(\d{6,})", segment.id)
            if not match:
                raise ValueError(f"invalid stable segment ID: {segment.id}")
            segment_numbers.append(int(match.group(1)))
            if (segment.speaker is None) != (segment.unknown_id is not None):
                raise ValueError(f"inconsistent UNKNOWN provenance for {segment.id}")
            if segment.unknown_id:
                unknown_match = re.fullmatch(r"UNK_(\d{6,})", segment.unknown_id)
                if not unknown_match:
                    raise ValueError(f"invalid stable UNKNOWN ID: {segment.unknown_id}")
                unknown_numbers.append(int(unknown_match.group(1)))
        if segment_numbers != sorted(set(segment_numbers)):
            raise ValueError("segment IDs must be unique and monotonically increasing")
        if unknown_numbers != sorted(set(unknown_numbers)):
            raise ValueError("UNKNOWN IDs must be unique and monotonically increasing")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "meeting": {
                "source": self.source,
                "duration": self.duration,
                "language": self.language,
                "language_probability": self.language_probability,
            },
            "speakers": [speaker.to_dict() for speaker in self.speakers],
            "segments": [segment.to_dict() for segment in self.segments],
            "review": self.review.to_dict(),
        }
