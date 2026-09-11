from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ihatemeetings.models.transcript import ReviewAssignment, Transcript, TranscriptSegment, Word


@dataclass(frozen=True)
class EffectiveAttribution:
    label: str
    original_cluster: str | None
    target_cluster: str | None
    identity_id: str | None
    display_name: str | None
    layer: str
    method: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "original_cluster": self.original_cluster,
            "target_cluster": self.target_cluster,
            "identity": (
                {"id": self.identity_id, "display_name": self.display_name}
                if self.identity_id and self.display_name
                else None
            ),
            "layer": self.layer,
            "method": self.method,
        }


@dataclass(frozen=True)
class EffectiveSegment:
    id: str
    unknown_id: str | None
    start: float
    end: float
    text: str
    words: tuple[Word, ...]
    confidence: None
    attribution: EffectiveAttribution
    source_segment_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "active",
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "words": [word.to_dict() for word in self.words],
            "speaker": self.attribution.to_dict(),
            "confidence": self.confidence,
            "source_segment_ids": list(self.source_segment_ids),
        }


def effective_segments(transcript: Transcript) -> tuple[EffectiveSegment, ...]:
    by_id = {segment.id: segment for segment in transcript.segments}
    effective: list[EffectiveSegment] = []
    for segment in transcript.segments:
        if segment.review.status != "active":
            continue
        parts = [segment]
        for merged_id in segment.review.merged_segment_ids:
            merged = by_id.get(merged_id)
            if merged is not None:
                parts.append(merged)
        effective.append(
            EffectiveSegment(
                id=segment.id,
                unknown_id=segment.unknown_id,
                start=min(part.start for part in parts),
                end=max(part.end for part in parts),
                text=" ".join(part.text.strip() for part in parts if part.text.strip()),
                words=tuple(word for part in parts for word in part.words),
                confidence=segment.confidence,
                attribution=effective_attribution(transcript, segment),
                source_segment_ids=tuple(part.id for part in parts),
            )
        )
    return tuple(effective)


def effective_attribution(
    transcript: Transcript, segment: TranscriptSegment
) -> EffectiveAttribution:
    original_cluster = segment.speaker.cluster if segment.speaker else None
    if segment.review.speaker_assignment is not None:
        return _assignment_attribution(
            transcript,
            segment.review.speaker_assignment,
            original_cluster,
            "segment_manual_override",
        )
    if original_cluster is not None:
        cluster_reviews = {
            item.cluster: item.assignment for item in transcript.review.cluster_assignments
        }
        if original_cluster in cluster_reviews:
            return _assignment_attribution(
                transcript,
                cluster_reviews[original_cluster],
                original_cluster,
                "cluster_manual_identity",
            )
        speaker = next(
            (item for item in transcript.speakers if item.cluster == original_cluster),
            segment.speaker,
        )
        if speaker is not None and speaker.name:
            return EffectiveAttribution(
                speaker.name,
                original_cluster,
                original_cluster,
                speaker.identity.id if speaker.identity else None,
                speaker.name,
                "phase4_resolution",
                speaker.resolver,
            )
        return EffectiveAttribution(
            original_cluster,
            original_cluster,
            original_cluster,
            None,
            None,
            "anonymous_cluster",
            None,
        )
    return EffectiveAttribution("UNKNOWN [?]", None, None, None, None, "phase3_unknown", None)


def same_effective_speaker(left: EffectiveAttribution, right: EffectiveAttribution) -> bool:
    if left.identity_id is not None or right.identity_id is not None:
        return left.identity_id is not None and left.identity_id == right.identity_id
    left_cluster = left.target_cluster or left.original_cluster
    right_cluster = right.target_cluster or right.original_cluster
    return left_cluster == right_cluster


def _assignment_attribution(
    transcript: Transcript,
    assignment: ReviewAssignment,
    original_cluster: str | None,
    layer: str,
) -> EffectiveAttribution:
    if assignment.identity is not None:
        return EffectiveAttribution(
            assignment.identity.display_name,
            original_cluster,
            original_cluster,
            assignment.identity.id,
            assignment.identity.display_name,
            layer,
            assignment.method,
        )
    target = assignment.cluster
    assert target is not None
    cluster_reviews = {
        item.cluster: item.assignment for item in transcript.review.cluster_assignments
    }
    if target in cluster_reviews and cluster_reviews[target].identity is not None:
        identity = cluster_reviews[target].identity
        assert identity is not None
        return EffectiveAttribution(
            identity.display_name,
            original_cluster,
            target,
            identity.id,
            identity.display_name,
            layer,
            assignment.method,
        )
    speaker = next((item for item in transcript.speakers if item.cluster == target), None)
    if speaker is not None and speaker.name:
        return EffectiveAttribution(
            speaker.name,
            original_cluster,
            target,
            speaker.identity.id if speaker.identity else None,
            speaker.name,
            layer,
            assignment.method,
        )
    return EffectiveAttribution(
        target, original_cluster, target, None, None, layer, assignment.method
    )


def canonical_payload(transcript: Transcript) -> dict[str, Any]:
    payload = transcript.to_dict()
    effective = {segment.id: segment for segment in effective_segments(transcript)}
    for record in payload["segments"]:
        segment = effective.get(record["id"])
        record["effective"] = (
            segment.to_dict()
            if segment
            else {
                "status": record["review"]["status"],
                "merged_into": record["review"]["merged_into"],
            }
        )
    return payload
