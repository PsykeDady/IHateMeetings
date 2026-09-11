from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ihatemeetings.errors import IHMError
from ihatemeetings.models import SpeakerIdentity

_CLUSTER_PATTERN = re.compile(r"SPEAKER_\d+")
_MARKDOWN_PARTICIPANT = re.compile(r"^\s*[-*]\s+(.+?)\s*$")


@dataclass(frozen=True)
class ManualSpeakerMapping:
    cluster: str
    identity: SpeakerIdentity

    def __post_init__(self) -> None:
        if not _CLUSTER_PATTERN.fullmatch(self.cluster):
            raise ValueError("manual mappings require a SPEAKER_NN cluster")


@dataclass(frozen=True)
class SpeakerAnchor:
    identity: SpeakerIdentity
    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("speaker anchors cannot be empty")


@dataclass(frozen=True)
class ResolutionConfig:
    manual_mappings: tuple[ManualSpeakerMapping, ...] = field(default_factory=tuple)
    anchors: tuple[SpeakerAnchor, ...] = field(default_factory=tuple)
    participants: tuple[SpeakerIdentity, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        clusters = [mapping.cluster for mapping in self.manual_mappings]
        if len(clusters) != len(set(clusters)):
            raise ValueError("each speaker cluster may have only one manual mapping")
        identities = (
            [mapping.identity for mapping in self.manual_mappings]
            + [anchor.identity for anchor in self.anchors]
            + list(self.participants)
        )
        names_by_id: dict[str, str] = {}
        for identity in identities:
            previous = names_by_id.setdefault(identity.id, identity.display_name)
            if previous != identity.display_name:
                raise ValueError(f"identity ID '{identity.id}' has conflicting display names")

    @property
    def requested(self) -> bool:
        return bool(self.manual_mappings or self.anchors or self.participants)


def parse_speaker_mapping(value: str) -> ManualSpeakerMapping:
    cluster, separator, name = value.partition("=")
    cluster = cluster.strip()
    name = name.strip()
    if not separator or not _CLUSTER_PATTERN.fullmatch(cluster) or not name:
        raise ValueError("expected SPEAKER_NN=Name with a non-empty name")
    return ManualSpeakerMapping(cluster, identity_from_name(name))


def load_resolution_config(
    *,
    cli_mappings: tuple[ManualSpeakerMapping, ...] = (),
    speaker_map_path: Path | None = None,
    anchors_path: Path | None = None,
    context_path: Path | None = None,
) -> ResolutionConfig:
    file_mappings = _load_manual_map(speaker_map_path) if speaker_map_path else ()
    mappings = _merge_manual_mappings(file_mappings, cli_mappings)
    anchors = _load_anchors(anchors_path) if anchors_path else ()
    participants = _load_context(context_path) if context_path else ()
    return ResolutionConfig(mappings, anchors, participants)


def identity_from_name(display_name: str, identity_id: str | None = None) -> SpeakerIdentity:
    name = display_name.strip()
    if not name:
        raise IHMError("Speaker display names cannot be empty.")
    candidate_id = identity_id.strip() if identity_id else _slugify(name)
    if not candidate_id or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", candidate_id):
        raise IHMError(
            f"Invalid speaker identity ID '{candidate_id}'.",
            "Use lowercase letters, digits and single hyphens.",
        )
    return SpeakerIdentity(candidate_id, name)


def _load_manual_map(path: Path) -> tuple[ManualSpeakerMapping, ...]:
    payload = _read_yaml(path)
    speakers = payload.get("speakers") if isinstance(payload, dict) else None
    if not isinstance(speakers, dict):
        raise IHMError(f"Speaker map '{path}' must contain a 'speakers' mapping.")
    mappings: list[ManualSpeakerMapping] = []
    for cluster, value in speakers.items():
        if not isinstance(cluster, str) or not _CLUSTER_PATTERN.fullmatch(cluster):
            raise IHMError(f"Invalid speaker cluster '{cluster}' in '{path}'.")
        if isinstance(value, str):
            identity = identity_from_name(value)
        elif isinstance(value, dict):
            name = value.get("name") or value.get("display_name")
            identity_id = value.get("id")
            if not isinstance(name, str) or (
                identity_id is not None and not isinstance(identity_id, str)
            ):
                raise IHMError(f"Invalid identity for '{cluster}' in '{path}'.")
            identity = identity_from_name(name, identity_id)
        else:
            raise IHMError(f"Invalid identity for '{cluster}' in '{path}'.")
        mappings.append(ManualSpeakerMapping(cluster, identity))
    return tuple(mappings)


def _load_anchors(path: Path) -> tuple[SpeakerAnchor, ...]:
    payload = _read_yaml(path)
    speakers = payload.get("speakers") if isinstance(payload, dict) else None
    if not isinstance(speakers, list):
        raise IHMError(f"Anchor file '{path}' must contain a 'speakers' list.")
    anchors: list[SpeakerAnchor] = []
    seen_ids: dict[str, str] = {}
    for entry in speakers:
        if not isinstance(entry, dict):
            raise IHMError(f"Every speaker in '{path}' must be a mapping.")
        name = entry.get("name") or entry.get("display_name")
        identity_id = entry.get("id")
        values = entry.get("anchors")
        if not isinstance(name, str) or not isinstance(values, list):
            raise IHMError(f"Every speaker in '{path}' requires a name and anchors list.")
        if identity_id is not None and not isinstance(identity_id, str):
            raise IHMError(f"Speaker identity IDs in '{path}' must be strings.")
        identity = identity_from_name(name, identity_id)
        previous_name = seen_ids.setdefault(identity.id, identity.display_name)
        if previous_name != identity.display_name:
            raise IHMError(f"Identity ID '{identity.id}' has conflicting names in '{path}'.")
        for value in values:
            text = value.get("text") if isinstance(value, dict) else value
            if not isinstance(text, str) or not text.strip():
                raise IHMError(f"Anchors for '{name}' in '{path}' must be non-empty text.")
            anchors.append(SpeakerAnchor(identity, text.strip()))
    return tuple(anchors)


def _load_context(path: Path) -> tuple[SpeakerIdentity, ...]:
    text = _read_text(path)
    if path.suffix.lower() in {".md", ".markdown"}:
        names = _markdown_participants(text)
    else:
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise IHMError(f"Invalid YAML in context file '{path}': {exc}") from exc
        values = payload.get("participants") if isinstance(payload, dict) else None
        if not isinstance(values, list):
            raise IHMError(f"Context file '{path}' must contain a 'participants' list.")
        names = []
        for value in values:
            if isinstance(value, str):
                names.append((value, None))
            elif isinstance(value, dict):
                name = value.get("name") or value.get("display_name")
                identity_id = value.get("id")
                if not isinstance(name, str) or (
                    identity_id is not None and not isinstance(identity_id, str)
                ):
                    raise IHMError(f"Invalid participant in context file '{path}'.")
                names.append((name, identity_id))
            else:
                raise IHMError(f"Invalid participant in context file '{path}'.")
    participants = tuple(identity_from_name(name, identity_id) for name, identity_id in names)
    if len({participant.id for participant in participants}) != len(participants):
        raise IHMError(f"Context file '{path}' contains duplicate participant identities.")
    return participants


def _markdown_participants(text: str) -> list[tuple[str, None]]:
    names: list[tuple[str, None]] = []
    in_participants = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.casefold() in {"participants:", "## participants", "# participants"}:
            in_participants = True
            continue
        if in_participants and (stripped.endswith(":") or stripped.startswith("#")):
            break
        if in_participants:
            match = _MARKDOWN_PARTICIPANT.fullmatch(line)
            if match:
                names.append((match.group(1).strip(), None))
    if not names:
        raise IHMError("Markdown context must contain a Participants list.")
    return names


def _merge_manual_mappings(
    file_mappings: tuple[ManualSpeakerMapping, ...],
    cli_mappings: tuple[ManualSpeakerMapping, ...],
) -> tuple[ManualSpeakerMapping, ...]:
    merged = {mapping.cluster: mapping for mapping in file_mappings}
    for mapping in cli_mappings:
        merged[mapping.cluster] = mapping
    return tuple(merged[cluster] for cluster in sorted(merged))


def _read_yaml(path: Path) -> Any:
    text = _read_text(path)
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise IHMError(f"Invalid YAML in '{path}': {exc}") from exc


def _read_text(path: Path) -> str:
    if not path.exists():
        raise IHMError(f"Configuration file not found: {path}")
    if not path.is_file():
        raise IHMError(f"Configuration path is not a file: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IHMError(f"Cannot read configuration file '{path}': {exc}") from exc


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")
