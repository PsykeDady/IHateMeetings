from __future__ import annotations

from collections import defaultdict

from ihatemeetings.diarization.base import DiarizationTurn
from ihatemeetings.models import SpeakerCandidate, Word, WordSpeakerAssignment

GAP_TOLERANCE_SECONDS = 0.25
MIN_WINNER_COVERAGE = 0.5
MIN_WINNER_SHARE = 0.6


def attribute_words(
    words: tuple[Word, ...], turns: tuple[DiarizationTurn, ...]
) -> tuple[Word, ...]:
    return tuple(_attribute_word(word, turns) for word in words)


def _attribute_word(word: Word, turns: tuple[DiarizationTurn, ...]) -> Word:
    if word.start is None or word.end is None:
        return _with_assignment(word, WordSpeakerAssignment(None, "missing_word_timestamps"))
    duration = word.end - word.start
    if duration <= 0:
        return _with_assignment(word, WordSpeakerAssignment(None, "zero_duration_word"))

    overlaps: dict[str, float] = defaultdict(float)
    for turn in turns:
        overlap = max(0.0, min(word.end, turn.end) - max(word.start, turn.start))
        if overlap:
            overlaps[turn.speaker_id] += overlap
    candidates = tuple(
        SpeakerCandidate(speaker_id, overlap)
        for speaker_id, overlap in sorted(overlaps.items(), key=lambda item: (-item[1], item[0]))
    )
    if candidates:
        winner = candidates[0]
        total_overlap = sum(candidate.overlap for candidate in candidates)
        coverage = min(1.0, winner.overlap / duration)
        share = winner.overlap / total_overlap
        tied = len(candidates) > 1 and abs(winner.overlap - candidates[1].overlap) < 1e-9
        speaker_id = (
            winner.speaker_id
            if not tied and coverage >= MIN_WINNER_COVERAGE and share >= MIN_WINNER_SHARE
            else None
        )
        method = "temporal_overlap" if speaker_id else "ambiguous_overlap"
        return _with_assignment(
            word,
            WordSpeakerAssignment(speaker_id, method, winner.overlap, coverage, candidates),
        )

    previous = [turn for turn in turns if 0 <= word.start - turn.end <= GAP_TOLERANCE_SECONDS]
    following = [turn for turn in turns if 0 <= turn.start - word.end <= GAP_TOLERANCE_SECONDS]
    if previous and following:
        left = max(previous, key=lambda turn: turn.end)
        right = min(following, key=lambda turn: turn.start)
        if left.speaker_id == right.speaker_id:
            return _with_assignment(
                word, WordSpeakerAssignment(left.speaker_id, "short_gap_bridge")
            )
    return _with_assignment(word, WordSpeakerAssignment(None, "no_temporal_evidence"))


def _with_assignment(word: Word, assignment: WordSpeakerAssignment) -> Word:
    return Word(word.text, word.start, word.end, word.confidence, assignment)
