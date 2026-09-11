import pytest

from ihatemeetings.config.defaults import RuntimeConfig
from ihatemeetings.diarization import DiarizationResult, DiarizationTurn, attribute_words
from ihatemeetings.errors import IHMError
from ihatemeetings.models import TranscriptSegment, Word
from ihatemeetings.pipeline.transcribe import _build_transcript, _diarize


def test_diarization_turns_allow_overlap_and_serialize_without_fake_confidence():
    result = DiarizationResult(
        "test",
        "1",
        "model",
        "completed",
        (
            DiarizationTurn("SPEAKER_00", 0.0, 1.0),
            DiarizationTurn("SPEAKER_01", 0.5, 1.5),
        ),
    )

    assert result.to_dict()["turns"][0]["confidence"] is None
    assert result.turns[0].end > result.turns[1].start


def test_diarization_turns_must_be_ordered():
    with pytest.raises(ValueError, match="ordered"):
        DiarizationResult(
            "test",
            "1",
            "model",
            "completed",
            (
                DiarizationTurn("SPEAKER_00", 1.0, 2.0),
                DiarizationTurn("SPEAKER_01", 0.0, 0.5),
            ),
        )


def test_word_inside_turn_is_attributed_by_temporal_overlap():
    word = attribute_words(
        (Word("hello", 0.2, 0.6, 0.9),),
        (DiarizationTurn("SPEAKER_00", 0.0, 1.0),),
    )[0]

    assert word.speaker.speaker_id == "SPEAKER_00"
    assert word.speaker.method == "temporal_overlap"
    assert word.speaker.word_coverage == pytest.approx(1.0)


def test_boundary_word_uses_dominant_overlap():
    word = attribute_words(
        (Word("boundary", 0.4, 0.8, None),),
        (
            DiarizationTurn("SPEAKER_00", 0.0, 0.66),
            DiarizationTurn("SPEAKER_01", 0.66, 1.0),
        ),
    )[0]

    assert word.speaker.speaker_id == "SPEAKER_00"
    assert len(word.speaker.candidates) == 2


def test_equal_overlap_remains_unassigned():
    word = attribute_words(
        (Word("overlap", 0.4, 0.8, None),),
        (
            DiarizationTurn("SPEAKER_00", 0.0, 1.0),
            DiarizationTurn("SPEAKER_01", 0.0, 1.0),
        ),
    )[0]

    assert word.speaker.speaker_id is None
    assert word.speaker.method == "ambiguous_overlap"


def test_short_gap_is_bridged_only_for_same_surrounding_speaker():
    word = attribute_words(
        (Word("gap", 1.05, 1.15, None),),
        (
            DiarizationTurn("SPEAKER_00", 0.0, 1.0),
            DiarizationTurn("SPEAKER_00", 1.2, 2.0),
        ),
    )[0]

    assert word.speaker.speaker_id == "SPEAKER_00"
    assert word.speaker.method == "short_gap_bridge"


def test_word_without_reliable_evidence_remains_unassigned():
    words = attribute_words(
        (Word("far", 2.0, 2.2, None), Word("unknown", None, None, None)),
        (DiarizationTurn("SPEAKER_00", 0.0, 1.0),),
    )

    assert words[0].speaker.speaker_id is None
    assert words[0].speaker.method == "no_temporal_evidence"
    assert words[1].speaker.method == "missing_word_timestamps"


def test_transcript_reconstruction_creates_cluster_turns_without_changing_words():
    segment = TranscriptSegment(
        "segment-000001",
        0.0,
        1.0,
        "Ciao iniziamo",
        (Word("Ciao", 0.0, 0.4, 0.9), Word("iniziamo", 0.5, 1.0, 0.8)),
    )
    diarization = DiarizationResult(
        "test",
        "1",
        "model",
        "completed",
        (
            DiarizationTurn("SPEAKER_00", 0.0, 0.45),
            DiarizationTurn("SPEAKER_01", 0.45, 1.0),
        ),
    )

    transcript = _build_transcript(1.0, "it", 0.99, "meeting.wav", (segment,), diarization)

    assert transcript.schema_version == 5
    assert [item.text for item in transcript.segments] == ["Ciao", "iniziamo"]
    assert [item.speaker.cluster for item in transcript.segments] == [
        "SPEAKER_00",
        "SPEAKER_01",
    ]
    assert " ".join(item.text for item in transcript.segments) == segment.text


def test_explicit_diarization_preserves_transcription_when_model_is_missing(monkeypatch):
    monkeypatch.setattr(
        "ihatemeetings.pipeline.transcribe.diarization_runtime_available", lambda: True
    )

    def missing_model(_override):
        raise IHMError("model missing", "download it explicitly")

    monkeypatch.setattr(
        "ihatemeetings.pipeline.transcribe.resolve_diarization_model", missing_model
    )
    messages = []

    result = _diarize(
        None,
        "cpu",
        RuntimeConfig(diarize=True),
        None,
        messages.append,
    )

    assert result.status == "unavailable"
    assert result.turns == ()
    assert "model missing" in result.warnings[0]
    assert any("Diarization unavailable" in message for message in messages)
