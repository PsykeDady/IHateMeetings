from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ihatemeetings.errors import IHMError
from ihatemeetings.exporters.transcript import render_all
from ihatemeetings.models import (
    ClusterReview,
    IdentityCandidate,
    IdentityEvidence,
    ReviewAssignment,
    SegmentReview,
    Speaker,
    SpeakerCandidate,
    SpeakerIdentity,
    Transcript,
    TranscriptReview,
    TranscriptSegment,
    Word,
    WordSpeakerAssignment,
)


@dataclass(frozen=True)
class LoadedReview:
    transcript: Transcript
    revisions: tuple[dict[str, Any], ...]
    migrated: bool
    migration_map: dict[str, str]


def load_review(output_dir: Path) -> LoadedReview:
    job_dir = output_dir.resolve()
    canonical_path = job_dir / "transcript.json"
    if not canonical_path.is_file():
        raise IHMError(f"Canonical transcript not found: {canonical_path}.")
    try:
        payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IHMError(f"Cannot read canonical transcript '{canonical_path}': {exc}") from exc
    version = payload.get("schema_version")
    if version not in {4, 5}:
        raise IHMError(
            f"Review supports canonical schema v4 or v5, found v{version}.",
            "Regenerate the transcript with a compatible IHateMeetings release.",
        )
    transcript, migration_map = _parse_transcript(payload, migrate=version == 4)
    revisions_path = job_dir / "review" / "revisions.json"
    revisions: tuple[dict[str, Any], ...] = ()
    if revisions_path.exists():
        try:
            audit = json.loads(revisions_path.read_text(encoding="utf-8"))
            if audit.get("schema_version") != 1 or not isinstance(audit.get("revisions"), list):
                raise ValueError("unsupported review audit structure")
            revisions = tuple(audit["revisions"])
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise IHMError(f"Cannot read review history '{revisions_path}': {exc}") from exc
    return LoadedReview(transcript, revisions, version == 4, migration_map)


def save_review(
    output_dir: Path,
    transcript: Transcript,
    revisions: tuple[dict[str, Any], ...],
) -> tuple[Path, ...]:
    job_dir = output_dir.resolve()
    review_dir = job_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    rendered = render_all(transcript)
    rendered["review/revisions.json"] = (
        json.dumps(
            {
                "schema_version": 1,
                "transcript_schema_version": transcript.schema_version,
                "revisions": list(revisions),
            },
            indent=2,
        )
        + "\n"
    )
    paths = {name: job_dir / name for name in rendered}
    _transactional_write({paths[name]: content for name, content in rendered.items()})
    return tuple(paths.values())


def _transactional_write(files: dict[Path, str]) -> None:
    originals: dict[Path, bytes | None] = {}
    temporaries: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        for path, content in files.items():
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            originals[path] = path.read_bytes() if path.exists() else None
            descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            temporary = Path(name)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.chmod(0o600)
            temporaries[path] = temporary
        for path, temporary in temporaries.items():
            os.replace(temporary, path)
            replaced.append(path)
    except BaseException:
        for path in reversed(replaced):
            original = originals[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_bytes(path, original)
        raise
    finally:
        for temporary in temporaries.values():
            temporary.unlink(missing_ok=True)


def _atomic_bytes(path: Path, content: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.rollback.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _parse_transcript(
    payload: dict[str, Any], *, migrate: bool
) -> tuple[Transcript, dict[str, str]]:
    meeting = payload.get("meeting")
    records = payload.get("segments")
    if not isinstance(meeting, dict) or not isinstance(records, list):
        raise IHMError("Canonical transcript is missing meeting or segment data.")
    if migrate:
        old_ids = [record.get("id") for record in records if isinstance(record, dict)]
        if (
            len(old_ids) != len(records)
            or any(not isinstance(value, str) or not value for value in old_ids)
            or len(old_ids) != len(set(old_ids))
        ):
            raise IHMError("Schema v4 transcript contains duplicate or missing segment IDs.")
    migration_map = (
        {
            str(record.get("id") or ""): f"SEG_{index:06d}"
            for index, record in enumerate(records, 1)
            if isinstance(record, dict)
        }
        if migrate
        else {}
    )
    speakers = tuple(_parse_speaker(value, migration_map) for value in payload.get("speakers", []))
    segments = []
    unknown_index = 0
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            raise IHMError("Canonical transcript contains an invalid segment record.")
        old_id = str(record.get("id") or "")
        segment_id = f"SEG_{index:06d}" if migrate else old_id
        original = record.get("original") if not migrate else record
        if not isinstance(original, dict):
            raise IHMError(f"Segment {segment_id} is missing its original state.")
        speaker = (
            _parse_speaker(original["speaker"], migration_map) if original.get("speaker") else None
        )
        unknown_id = record.get("unknown_id")
        if migrate and speaker is None:
            unknown_index += 1
            unknown_id = f"UNK_{unknown_index:06d}"
        review = _parse_segment_review(record.get("review")) if not migrate else SegmentReview()
        segments.append(
            TranscriptSegment(
                segment_id,
                float(original["start"]),
                float(original["end"]),
                str(original["text"]),
                tuple(_parse_word(word) for word in original.get("words", [])),
                speaker,
                original.get("confidence"),
                str(unknown_id) if unknown_id else None,
                review,
            )
        )
    _validate_ids(tuple(segments))
    review = (
        _parse_transcript_review(payload.get("review"))
        if not migrate
        else TranscriptReview(migrated_from_schema=4)
    )
    return (
        Transcript(
            float(meeting["duration"]),
            meeting.get("language"),
            meeting.get("language_probability"),
            str(meeting.get("source", "")),
            tuple(segments),
            speakers,
            5,
            review,
        ),
        migration_map,
    )


def _parse_speaker(value: dict[str, Any], id_map: dict[str, str] | None = None) -> Speaker:
    identity_value = value.get("identity")
    identity = _parse_identity(identity_value) if identity_value else None
    resolution = value.get("resolution") or {}
    evidence = tuple(_parse_evidence(item, id_map) for item in resolution.get("evidence", []))
    candidates = tuple(
        IdentityCandidate(
            _parse_identity(item["identity"]),
            float(item["confidence"]),
            tuple(
                _parse_evidence(evidence_item, id_map) for evidence_item in item.get("evidence", [])
            ),
        )
        for item in resolution.get("candidates", [])
    )
    return Speaker(
        str(value["cluster"]),
        identity,
        resolution.get("status", "unresolved"),
        resolution.get("confidence"),
        resolution.get("resolver"),
        evidence,
        candidates,
        tuple(resolution.get("warnings", [])),
    )


def _parse_identity(value: dict[str, Any]) -> SpeakerIdentity:
    return SpeakerIdentity(str(value["id"]), str(value["display_name"]))


def _parse_evidence(
    value: dict[str, Any], id_map: dict[str, str] | None = None
) -> IdentityEvidence:
    segment_id = value.get("segment_id")
    if segment_id is not None and id_map:
        segment_id = id_map.get(str(segment_id), str(segment_id))
    return IdentityEvidence(
        str(value["type"]),
        str(value["value"]),
        float(value["confidence"]),
        str(value["method"]),
        segment_id,
    )


def _parse_word(value: dict[str, Any]) -> Word:
    speaker_value = value.get("speaker")
    assignment = None
    if speaker_value:
        assignment = WordSpeakerAssignment(
            speaker_value.get("speaker_id"),
            str(speaker_value["method"]),
            float(speaker_value.get("overlap", 0.0)),
            float(speaker_value.get("word_coverage", 0.0)),
            tuple(
                SpeakerCandidate(str(item["speaker_id"]), float(item["overlap"]))
                for item in speaker_value.get("candidates", [])
            ),
        )
    return Word(
        str(value["text"]),
        value.get("start"),
        value.get("end"),
        value.get("confidence"),
        assignment,
    )


def _parse_assignment(value: dict[str, Any]) -> ReviewAssignment:
    identity = _parse_identity(value["identity"]) if value.get("identity") else None
    return ReviewAssignment(
        str(value["kind"]), identity, value.get("cluster"), str(value["method"])
    )


def _parse_segment_review(value: Any) -> SegmentReview:
    if not isinstance(value, dict):
        return SegmentReview()
    assignment = value.get("speaker_assignment")
    return SegmentReview(
        str(value.get("status", "active")),
        bool(value.get("accepted", False)),
        _parse_assignment(assignment) if assignment else None,
        tuple(str(item) for item in value.get("merged_segment_ids", [])),
        value.get("merged_into"),
    )


def _parse_transcript_review(value: Any) -> TranscriptReview:
    if not isinstance(value, dict):
        return TranscriptReview()
    assignments = tuple(
        ClusterReview(str(item["cluster"]), _parse_assignment(item["assignment"]))
        for item in value.get("cluster_assignments", [])
    )
    return TranscriptReview(assignments, value.get("migrated_from_schema"))


def _validate_ids(segments: tuple[TranscriptSegment, ...]) -> None:
    segment_ids = [segment.id for segment in segments]
    unknown_ids = [segment.unknown_id for segment in segments if segment.unknown_id]
    if len(segment_ids) != len(set(segment_ids)) or any(not value for value in segment_ids):
        raise IHMError("Canonical transcript contains duplicate or empty segment IDs.")
    if len(unknown_ids) != len(set(unknown_ids)):
        raise IHMError("Canonical transcript contains duplicate UNKNOWN IDs.")
    segment_numbers = []
    for value in segment_ids:
        match = re.fullmatch(r"SEG_(\d{6,})", value)
        if not match:
            raise IHMError(f"Canonical transcript contains invalid segment ID '{value}'.")
        segment_numbers.append(int(match.group(1)))
    if segment_numbers != sorted(segment_numbers) or len(segment_numbers) != len(
        set(segment_numbers)
    ):
        raise IHMError("Canonical segment IDs are not monotonically increasing.")
    unknown_numbers = []
    for value in unknown_ids:
        match = re.fullmatch(r"UNK_(\d{6,})", value)
        if not match:
            raise IHMError(f"Canonical transcript contains invalid UNKNOWN ID '{value}'.")
        unknown_numbers.append(int(match.group(1)))
    if unknown_numbers != sorted(unknown_numbers):
        raise IHMError("Canonical UNKNOWN IDs are not monotonically increasing.")
    for segment in segments:
        if (segment.speaker is None) != (segment.unknown_id is not None):
            raise IHMError(f"Segment {segment.id} has inconsistent original UNKNOWN provenance.")
