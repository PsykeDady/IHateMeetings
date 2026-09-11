from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ihatemeetings.errors import IHMError
from ihatemeetings.models import (
    ClusterReview,
    ReviewAssignment,
    SegmentReview,
    TranscriptSegment,
)
from ihatemeetings.review.effective import (
    effective_attribution,
    effective_segments,
    same_effective_speaker,
)
from ihatemeetings.review.io import LoadedReview, load_review, save_review
from ihatemeetings.speakers.config import identity_from_name


class ReviewSession:
    def __init__(
        self,
        output_dir: Path,
        loaded: LoadedReview,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.transcript = loaded.transcript
        self.revisions = list(loaded.revisions)
        self._clock = clock or (lambda: datetime.now(UTC))
        self.migrated = loaded.migrated
        self.dirty = False
        if loaded.migrated:
            self._record(
                "schema_migration",
                tuple(loaded.migration_map.values()),
                {"schema_version": 4, "segment_ids": loaded.migration_map},
                {"schema_version": 5},
            )

    @classmethod
    def open(
        cls,
        output_dir: Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> ReviewSession:
        return cls(output_dir, load_review(output_dir), clock=clock)

    def save(self) -> tuple[Path, ...]:
        outputs = save_review(self.output_dir, self.transcript, tuple(self.revisions))
        self.dirty = False
        return outputs

    def find_segment(self, reference: str) -> TranscriptSegment:
        matches = [
            segment
            for segment in self.transcript.segments
            if segment.id == reference or segment.unknown_id == reference
        ]
        if not matches:
            kind = "UNKNOWN" if reference.startswith("UNK_") else "segment"
            raise IHMError(f"Unknown {kind} ID '{reference}'.")
        return matches[0]

    def list_segments(self, *, unknown_only: bool = False) -> tuple[TranscriptSegment, ...]:
        return tuple(
            segment
            for segment in self.transcript.segments
            if segment.review.status == "active"
            and (not unknown_only or segment.unknown_id is not None)
        )

    def assign_cluster(self, cluster: str, display_name: str) -> None:
        if cluster not in {speaker.cluster for speaker in self.transcript.speakers}:
            raise IHMError(f"Unknown speaker cluster '{cluster}'.")
        assignment = self._identity_assignment(display_name)
        before = self._cluster_state(cluster)
        reviews = {item.cluster: item for item in self.transcript.review.cluster_assignments}
        reviews[cluster] = ClusterReview(cluster, assignment)
        self.transcript = replace(
            self.transcript,
            review=replace(
                self.transcript.review,
                cluster_assignments=tuple(reviews[key] for key in sorted(reviews)),
            ),
        )
        self._record("assign_cluster_identity", (cluster,), before, self._cluster_state(cluster))

    def assign_segment(
        self,
        reference: str,
        *,
        display_name: str | None = None,
        cluster: str | None = None,
        operation: str = "assign_segment_identity",
    ) -> None:
        segment = self.find_segment(reference)
        if segment.review.status != "active":
            raise IHMError(f"Segment {segment.id} is not active and cannot be assigned.")
        assignment = self._assignment(display_name=display_name, cluster=cluster)
        before = self._segment_state(segment.id)
        review = replace(segment.review, speaker_assignment=assignment)
        self._replace_segment(replace(segment, review=review))
        self._record(operation, (segment.id,), before, self._segment_state(segment.id))

    def assign_unknown(
        self,
        reference: str,
        *,
        display_name: str | None = None,
        cluster: str | None = None,
    ) -> None:
        segment = self.find_segment(reference)
        if segment.unknown_id is None:
            raise IHMError(f"Segment {segment.id} was not originally UNKNOWN.")
        self.assign_segment(
            segment.id,
            display_name=display_name,
            cluster=cluster,
            operation="resolve_unknown",
        )

    def accept_segment(self, reference: str) -> None:
        segment = self.find_segment(reference)
        if segment.review.status != "active":
            raise IHMError(f"Segment {segment.id} is not active and cannot be accepted.")
        if segment.review.accepted:
            return
        before = self._segment_state(segment.id)
        self._replace_segment(replace(segment, review=replace(segment.review, accepted=True)))
        self._record("accept_segment", (segment.id,), before, self._segment_state(segment.id))

    def merge(
        self,
        first_reference: str,
        second_reference: str,
        *,
        display_name: str | None = None,
        cluster: str | None = None,
    ) -> None:
        first = self.find_segment(first_reference)
        second = self.find_segment(second_reference)
        if first.id == second.id:
            raise IHMError("A segment cannot be merged with itself.")
        if first.review.status != "active" or second.review.status != "active":
            raise IHMError("Only active segments can be merged.")
        positions = {segment.id: index for index, segment in enumerate(self.transcript.segments)}
        first_sources = (first.id, *first.review.merged_segment_ids)
        last_position = max(positions[source_id] for source_id in first_sources)
        if positions[second.id] != last_position + 1:
            raise IHMError("Segments must be adjacent and supplied in transcript order.")
        explicit = display_name is not None or cluster is not None
        first_attribution = effective_attribution(self.transcript, first)
        second_attribution = effective_attribution(self.transcript, second)
        if not same_effective_speaker(first_attribution, second_attribution) and not explicit:
            raise IHMError(
                "Segments have different effective speakers; provide --name or --cluster "
                "to resolve the merged attribution explicitly."
            )
        before = {
            first.id: self._segment_state(first.id),
            second.id: self._segment_state(second.id),
        }
        assignment = (
            self._assignment(display_name=display_name, cluster=cluster) if explicit else None
        )
        first_review = replace(
            first.review,
            speaker_assignment=assignment or first.review.speaker_assignment,
            merged_segment_ids=(
                *first.review.merged_segment_ids,
                second.id,
                *second.review.merged_segment_ids,
            ),
        )
        second_review = SegmentReview(
            status="merged",
            accepted=second.review.accepted,
            speaker_assignment=second.review.speaker_assignment,
            merged_into=first.id,
        )
        self._replace_segments(
            {
                first.id: replace(first, review=first_review),
                second.id: replace(second, review=second_review),
            }
        )
        after = {
            first.id: self._segment_state(first.id),
            second.id: self._segment_state(second.id),
        }
        self._record("merge_segments", (first.id, second.id), before, after)

    def delete(self, reference: str) -> None:
        segment = self.find_segment(reference)
        if segment.review.status != "active":
            raise IHMError(f"Segment {segment.id} is not active and cannot be deleted.")
        before = self._segment_state(segment.id)
        self._replace_segment(replace(segment, review=replace(segment.review, status="deleted")))
        self._record("delete_segment", (segment.id,), before, self._segment_state(segment.id))

    def _assignment(self, *, display_name: str | None, cluster: str | None) -> ReviewAssignment:
        if (display_name is None) == (cluster is None):
            raise IHMError("Choose exactly one assignment target: a name or a cluster.")
        if cluster is not None:
            if cluster not in {speaker.cluster for speaker in self.transcript.speakers}:
                raise IHMError(f"Unknown speaker cluster '{cluster}'.")
            return ReviewAssignment("cluster", cluster=cluster)
        assert display_name is not None
        return self._identity_assignment(display_name)

    def _identity_assignment(self, display_name: str) -> ReviewAssignment:
        name = display_name.strip()
        known = [
            speaker.identity
            for speaker in self.transcript.speakers
            if speaker.identity is not None and speaker.identity.display_name == name
        ]
        for review in self.transcript.review.cluster_assignments:
            if review.assignment.identity and review.assignment.identity.display_name == name:
                known.append(review.assignment.identity)
        identity = known[0] if known else identity_from_name(name)
        return ReviewAssignment("identity", identity=identity)

    def _replace_segment(self, replacement: TranscriptSegment) -> None:
        self._replace_segments({replacement.id: replacement})

    def _replace_segments(self, replacements: dict[str, TranscriptSegment]) -> None:
        self.transcript = replace(
            self.transcript,
            segments=tuple(
                replacements.get(segment.id, segment) for segment in self.transcript.segments
            ),
        )

    def _segment_state(self, segment_id: str) -> dict[str, Any]:
        segment = next(item for item in self.transcript.segments if item.id == segment_id)
        effective = next(
            (item for item in effective_segments(self.transcript) if item.id == segment_id),
            None,
        )
        return {
            "id": segment.id,
            "unknown_id": segment.unknown_id,
            "original_speaker": segment.speaker.to_dict() if segment.speaker else None,
            "review": segment.review.to_dict(),
            "effective": effective.to_dict() if effective else None,
        }

    def _cluster_state(self, cluster: str) -> dict[str, Any]:
        original = next(item for item in self.transcript.speakers if item.cluster == cluster)
        override = next(
            (
                item.assignment
                for item in self.transcript.review.cluster_assignments
                if item.cluster == cluster
            ),
            None,
        )
        return {
            "cluster": cluster,
            "original": original.to_dict(),
            "review_assignment": override.to_dict() if override else None,
        }

    def _record(
        self,
        operation: str,
        targets: tuple[str, ...],
        before: Any,
        after: Any,
    ) -> None:
        revision = {
            "id": f"REV_{len(self.revisions) + 1:06d}",
            "operation": operation,
            "targets": list(targets),
            "before": before,
            "after": after,
            "method": "explicit_user_input" if operation != "schema_migration" else "migration",
            "timestamp": self._clock().isoformat(),
        }
        self.revisions.append(revision)
        self.dirty = True
