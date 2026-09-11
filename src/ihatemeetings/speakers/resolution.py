from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import replace
from difflib import SequenceMatcher

from ihatemeetings.errors import IHMError
from ihatemeetings.models import (
    IdentityCandidate,
    IdentityEvidence,
    ResolutionReport,
    Speaker,
    SpeakerIdentity,
    Transcript,
)
from ihatemeetings.speakers.config import ResolutionConfig, SpeakerAnchor

MIN_ANCHOR_TOKENS = 5
MIN_ANCHOR_CHARACTERS = 24
CANDIDATE_THRESHOLD = 0.85
RESOLUTION_THRESHOLD = 0.92
AMBIGUITY_THRESHOLD = 0.85
AMBIGUITY_MARGIN = 0.05


class SpeakerResolver(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Stable resolver name recorded in audit artifacts."""

    @abstractmethod
    def resolve(self, transcript: Transcript, config: ResolutionConfig) -> ResolutionReport:
        """Resolve anonymous clusters without changing Phase 3 word attribution."""


class ConservativeSpeakerResolver(SpeakerResolver):
    @property
    def name(self) -> str:
        return "conservative-v1"

    def resolve(self, transcript: Transcript, config: ResolutionConfig) -> ResolutionReport:
        available = {speaker.cluster for speaker in transcript.speakers}
        manual = {mapping.cluster: mapping.identity for mapping in config.manual_mappings}
        missing = sorted(set(manual) - available)
        if missing:
            raise IHMError(
                f"Manual speaker mapping references unknown cluster(s): {', '.join(missing)}.",
                "Run once without identity resolution and inspect transcript.json for cluster IDs.",
            )

        global_warnings: list[str] = []
        eligible_anchors = self._eligible_anchors(config, global_warnings)
        cluster_text = _cluster_text(transcript)
        anchor_matches = _match_anchors(eligible_anchors, cluster_text, global_warnings)
        speakers = tuple(
            self._resolve_cluster(speaker.cluster, manual, anchor_matches)
            for speaker in transcript.speakers
        )
        return ResolutionReport(self.name, config.requested, speakers, tuple(global_warnings))

    def _eligible_anchors(
        self, config: ResolutionConfig, warnings: list[str]
    ) -> tuple[SpeakerAnchor, ...]:
        participants = {participant.id for participant in config.participants}
        eligible: list[SpeakerAnchor] = []
        for anchor in config.anchors:
            normalized = normalize_anchor_text(anchor.text)
            if not _is_strong_anchor(normalized):
                warnings.append(
                    f"Ignored weak anchor for identity '{anchor.identity.id}': "
                    f"requires at least {MIN_ANCHOR_TOKENS} words and "
                    f"{MIN_ANCHOR_CHARACTERS} characters."
                )
                continue
            if participants and anchor.identity.id not in participants:
                warnings.append(
                    f"Ignored anchor identity '{anchor.identity.id}' because it is not in context."
                )
                continue
            eligible.append(anchor)
        return tuple(eligible)

    def _resolve_cluster(
        self,
        cluster: str,
        manual: dict[str, SpeakerIdentity],
        matches: dict[str, dict[str, tuple[SpeakerIdentity, list[IdentityEvidence]]]],
    ) -> Speaker:
        if cluster in manual:
            identity = manual[cluster]
            evidence = IdentityEvidence("manual_mapping", cluster, 1.0, "explicit_user_input")
            return Speaker(cluster, identity, "resolved", 1.0, self.name, (evidence,))

        candidates = []
        for identity, evidence in matches.get(cluster, {}).values():
            confidence = _combine_independent_confidence(evidence)
            candidates.append(IdentityCandidate(identity, confidence, tuple(evidence)))
        candidates.sort(key=lambda item: (-item.confidence, item.identity.id))
        candidate_tuple = tuple(candidates)
        strong = [item for item in candidates if item.confidence >= RESOLUTION_THRESHOLD]
        if len(strong) > 1:
            return Speaker(
                cluster,
                status="conflicting",
                resolver=self.name,
                candidates=candidate_tuple,
                warnings=("Multiple identities have strong anchor evidence.",),
            )
        if strong:
            selected = strong[0]
            return Speaker(
                cluster,
                selected.identity,
                "resolved",
                selected.confidence,
                self.name,
                selected.evidence,
                candidate_tuple,
            )
        if (
            len(candidates) > 1
            and candidates[0].confidence >= AMBIGUITY_THRESHOLD
            and candidates[0].confidence - candidates[1].confidence < AMBIGUITY_MARGIN
        ):
            return Speaker(
                cluster,
                status="ambiguous",
                resolver=self.name,
                candidates=candidate_tuple,
                warnings=("Top identity candidates are too close to select safely.",),
            )
        return Speaker(cluster, status="unresolved", resolver=self.name, candidates=candidate_tuple)


def apply_resolution(transcript: Transcript, report: ResolutionReport) -> Transcript:
    expected_clusters = [speaker.cluster for speaker in transcript.speakers]
    report_clusters = [speaker.cluster for speaker in report.speakers]
    if len(report_clusters) != len(set(report_clusters)) or set(report_clusters) != set(
        expected_clusters
    ):
        raise IHMError("Speaker resolver returned an invalid cluster set.")
    resolved = {speaker.cluster: speaker for speaker in report.speakers}
    segments = tuple(
        replace(segment, speaker=resolved.get(segment.speaker.cluster, segment.speaker))
        if segment.speaker is not None
        else segment
        for segment in transcript.segments
    )
    return replace(transcript, speakers=report.speakers, segments=segments)


def normalize_anchor_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = "".join(character if character.isalnum() else " " for character in normalized)
    return " ".join(normalized.split())


def _cluster_text(transcript: Transcript) -> dict[str, tuple[tuple[str, str], ...]]:
    segments: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for segment in transcript.segments:
        if segment.speaker is None:
            continue
        segments[segment.speaker.cluster].append((segment.id, normalize_anchor_text(segment.text)))
    return {cluster: tuple(cluster_segments) for cluster, cluster_segments in segments.items()}


def _match_anchors(
    anchors: tuple[SpeakerAnchor, ...],
    cluster_text: dict[str, tuple[tuple[str, str], ...]],
    warnings: list[str],
) -> dict[str, dict[str, tuple[SpeakerIdentity, list[IdentityEvidence]]]]:
    matches: dict[str, dict[str, tuple[SpeakerIdentity, list[IdentityEvidence]]]] = defaultdict(
        dict
    )
    for anchor in anchors:
        normalized_anchor = normalize_anchor_text(anchor.text)
        cluster_scores = []
        for cluster, segments in cluster_text.items():
            segment_scores = [
                (*_text_match(normalized_anchor, text), segment_id) for segment_id, text in segments
            ]
            score, method, segment_id = max(segment_scores, default=(0.0, "none", None))
            if score >= CANDIDATE_THRESHOLD:
                cluster_scores.append((cluster, score, method, segment_id))
        if len(cluster_scores) > 1:
            warnings.append(
                f"Ignored anchor for identity '{anchor.identity.id}' because it matched "
                "multiple speaker clusters."
            )
            continue
        if not cluster_scores:
            continue
        cluster, score, method, segment_id = cluster_scores[0]
        evidence = IdentityEvidence(
            "text_anchor",
            anchor.text,
            score,
            method,
            segment_id,
        )
        identity_entry = matches[cluster].setdefault(anchor.identity.id, (anchor.identity, []))
        identity_entry[1].append(evidence)
    return matches


def _text_match(anchor: str, text: str) -> tuple[float, str]:
    if not anchor or not text:
        return 0.0, "none"
    if f" {anchor} " in f" {text} ":
        return 0.99, "exact_normalized"
    anchor_words = anchor.split()
    text_words = text.split()
    minimum = max(1, len(anchor_words) - 1)
    maximum = min(len(text_words), len(anchor_words) + 1)
    best = 0.0
    for size in range(minimum, maximum + 1):
        for start in range(len(text_words) - size + 1):
            candidate = " ".join(text_words[start : start + size])
            best = max(best, SequenceMatcher(None, anchor, candidate).ratio())
    return best, "fuzzy_normalized" if best >= CANDIDATE_THRESHOLD else "none"


def _is_strong_anchor(normalized: str) -> bool:
    return len(normalized.split()) >= MIN_ANCHOR_TOKENS and len(normalized) >= MIN_ANCHOR_CHARACTERS


def _combine_independent_confidence(evidence: list[IdentityEvidence]) -> float:
    remaining_uncertainty = 1.0
    for item in evidence:
        remaining_uncertainty *= 1.0 - item.confidence
    return min(0.999, 1.0 - remaining_uncertainty)
