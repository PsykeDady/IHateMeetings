from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ResolutionStatus = Literal["resolved", "unresolved", "ambiguous", "conflicting"]


@dataclass(frozen=True)
class SpeakerIdentity:
    id: str
    display_name: str

    def __post_init__(self) -> None:
        if not self.id or not self.display_name.strip():
            raise ValueError("speaker identity ID and display name cannot be empty")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class IdentityEvidence:
    type: str
    value: str
    confidence: float
    method: str
    segment_id: str | None = None

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)
        if not self.type or not self.method:
            raise ValueError("identity evidence type and method cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IdentityCandidate:
    identity: SpeakerIdentity
    confidence: float
    evidence: tuple[IdentityEvidence, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "confidence": self.confidence,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class Speaker:
    cluster: str
    identity: SpeakerIdentity | None = None
    status: ResolutionStatus = "unresolved"
    confidence: float | None = None
    resolver: str | None = None
    evidence: tuple[IdentityEvidence, ...] = field(default_factory=tuple)
    candidates: tuple[IdentityCandidate, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.confidence is not None:
            _validate_confidence(self.confidence)
        if self.status == "resolved" and (self.identity is None or self.confidence is None):
            raise ValueError("a resolved speaker requires an identity and confidence")
        if self.status != "resolved" and self.identity is not None:
            raise ValueError("only resolved speakers may have a selected identity")

    @property
    def name(self) -> str | None:
        return self.identity.display_name if self.identity else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster": self.cluster,
            "identity": self.identity.to_dict() if self.identity else None,
            "resolution": {
                "status": self.status,
                "confidence": self.confidence,
                "resolver": self.resolver,
                "evidence": [item.to_dict() for item in self.evidence],
                "candidates": [candidate.to_dict() for candidate in self.candidates],
                "warnings": list(self.warnings),
            },
        }


@dataclass(frozen=True)
class ResolutionReport:
    resolver: str
    requested: bool
    speakers: tuple[Speaker, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolver": self.resolver,
            "requested": self.requested,
            "clusters": [speaker.to_dict() for speaker in self.speakers],
            "warnings": list(self.warnings),
        }


def _validate_confidence(value: float) -> None:
    if not 0 <= value <= 1:
        raise ValueError("identity confidence must be between zero and one")
