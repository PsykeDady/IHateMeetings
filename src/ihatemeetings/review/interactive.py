from __future__ import annotations

from collections.abc import Callable

from ihatemeetings.errors import IHMError
from ihatemeetings.review.effective import (
    effective_attribution,
    effective_segments,
    same_effective_speaker,
)
from ihatemeetings.review.service import ReviewSession
from ihatemeetings.utils.time import format_timestamp


def format_segment(session: ReviewSession, reference: str) -> str:
    segment = session.find_segment(reference)
    effective = next(
        (item for item in effective_segments(session.transcript) if item.id == segment.id),
        None,
    )
    original_label = (
        segment.speaker.name or segment.speaker.cluster if segment.speaker else "UNKNOWN [?]"
    )
    identity = f" · {segment.unknown_id}" if segment.unknown_id else ""
    lines = [
        f"{segment.id}{identity}",
        f"Status: {segment.review.status}",
        f"Original: {original_label}",
    ]
    if effective is not None:
        lines.extend(
            [
                f"Effective: {effective.attribution.label}",
                (
                    f"{format_timestamp(effective.start, milliseconds=True)} → "
                    f"{format_timestamp(effective.end, milliseconds=True)}"
                ),
                "",
                effective.text,
            ]
        )
    elif segment.review.merged_into:
        lines.append(f"Merged into: {segment.review.merged_into}")
    else:
        lines.extend(["", segment.text])
    return "\n".join(lines)


def format_speakers(session: ReviewSession) -> str:
    overrides = {
        item.cluster: item.assignment.identity.display_name
        for item in session.transcript.review.cluster_assignments
        if item.assignment.identity is not None
    }
    lines = []
    for speaker in session.transcript.speakers:
        original = speaker.name or "unresolved"
        reviewed = overrides.get(speaker.cluster)
        suffix = f" -> {reviewed} [manual]" if reviewed else ""
        lines.append(f"{speaker.cluster} · {original}{suffix}")
    return "\n".join(lines) if lines else "No diarization clusters."


def run_interactive(
    session: ReviewSession,
    *,
    unknown_only: bool = False,
    input_fn: Callable[[str], str] = input,
    emit: Callable[[str], None] = print,
) -> bool:
    index = 0
    while True:
        targets = session.list_segments(unknown_only=unknown_only)
        if not targets:
            emit("No matching active segments.")
            action = input_fn("[q] Save and quit · [Q] quit without saving: ")
            if action == "q":
                session.save()
                emit("Review saved; transcript exports regenerated without ML.")
                return True
            if action == "Q":
                emit("Review discarded; nothing was written.")
                return False
            continue
        if index >= len(targets):
            emit("Reached the end of the review set.")
            action = input_fn("[p] Previous · [j] jump · [q] save · [Q] discard: ")
            if action == "q":
                session.save()
                emit("Review saved; transcript exports regenerated without ML.")
                return True
            if action == "Q":
                emit("Review discarded; nothing was written.")
                return False
            if action == "p":
                index = len(targets) - 1
            elif action == "j":
                try:
                    target = session.find_segment(input_fn("Segment or UNKNOWN ID: ").strip())
                    index = next(
                        position for position, item in enumerate(targets) if item.id == target.id
                    )
                except (IHMError, StopIteration) as exc:
                    emit(f"Error: {exc}")
            continue
        current = targets[index]
        emit("─" * 48)
        emit(format_segment(session, current.id))
        emit("─" * 48)
        emit("[Enter/o] OK  [s] Skip  [a] Assign  [r] Rename cluster  [m] Merge next  [d] Delete")
        emit("[p] Previous  [j] Jump  [q] Save+quit  [Q] Discard")
        action = input_fn("Action: ")
        try:
            if action in {"", "o"}:
                session.accept_segment(current.id)
                index += 1
            elif action == "s":
                index += 1
            elif action == "p":
                index = max(0, index - 1)
            elif action == "j":
                target = session.find_segment(input_fn("Segment or UNKNOWN ID: ").strip())
                targets = session.list_segments(unknown_only=unknown_only)
                index = next(
                    position for position, item in enumerate(targets) if item.id == target.id
                )
            elif action == "a":
                assignment = _prompt_assignment(input_fn)
                session.assign_segment(current.id, **assignment)
                index += 1
            elif action == "r":
                if current.speaker is None:
                    raise IHMError("This segment has no original cluster to rename.")
                name = input_fn(f"Name for {current.speaker.cluster}: ").strip()
                session.assign_cluster(current.speaker.cluster, name)
                index += 1
            elif action == "m":
                next_segment = _next_original_active(session, current.id)
                if next_segment is None:
                    raise IHMError("There is no adjacent active segment to merge.")
                kwargs = {}
                first_attribution = effective_attribution(session.transcript, current)
                second_attribution = effective_attribution(session.transcript, next_segment)
                if not same_effective_speaker(first_attribution, second_attribution):
                    emit(
                        f"Speaker mismatch: {first_attribution.label} / {second_attribution.label}"
                    )
                    kwargs = _prompt_assignment(input_fn)
                session.merge(current.id, next_segment.id, **kwargs)
                index += 1
            elif action == "d":
                session.delete(current.id)
            elif action == "q":
                session.save()
                emit("Review saved; transcript exports regenerated without ML.")
                return True
            elif action == "Q":
                emit("Review discarded; nothing was written.")
                return False
            else:
                emit("Unknown action.")
        except (IHMError, StopIteration) as exc:
            emit(f"Error: {exc}")


def _prompt_assignment(input_fn: Callable[[str], str]) -> dict[str, str]:
    kind = input_fn("Target [n]ame or [c]luster: ").strip().lower()
    if kind == "n":
        return {"display_name": input_fn("Display name: ").strip()}
    if kind == "c":
        return {"cluster": input_fn("Cluster ID: ").strip()}
    raise IHMError("Choose 'n' for a display name or 'c' for a cluster.")


def _next_original_active(session: ReviewSession, segment_id: str):
    segments = session.transcript.segments
    position = next(index for index, item in enumerate(segments) if item.id == segment_id)
    current = segments[position]
    positions = {item.id: index for index, item in enumerate(segments)}
    last_position = max(
        positions[source_id] for source_id in (current.id, *current.review.merged_segment_ids)
    )
    if last_position + 1 >= len(segments):
        return None
    candidate = segments[last_position + 1]
    return candidate if candidate.review.status == "active" else None
