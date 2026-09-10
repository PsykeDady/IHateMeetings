from ihatemeetings.asr.models import model_cache_dir
from ihatemeetings.models import ASRResult, ASRSegment, Transcript, TranscriptSegment


def test_canonical_transcript_is_versioned_and_typed():
    transcript = Transcript(
        duration=12.5,
        language="it",
        language_probability=0.98,
        source="meeting.wav",
        segments=(TranscriptSegment("segment-000001", 1.0, 2.5, "Buongiorno."),),
    )

    payload = transcript.to_dict()

    assert payload["schema_version"] == 1
    assert payload["meeting"]["language"] == "it"
    assert payload["speakers"] == []
    assert payload["segments"][0]["speaker"] is None
    assert payload["segments"][0]["confidence"] is None


def test_raw_asr_result_preserves_backend_evidence():
    result = ASRResult(
        backend="test",
        backend_version="1",
        model="tiny",
        language="it",
        language_probability=0.9,
        duration=3.0,
        duration_after_vad=None,
        segments=(
            ASRSegment(
                start=0.0,
                end=1.0,
                text="Ciao",
                token_ids=(1, 2),
                avg_logprob=-0.2,
                no_speech_prob=0.01,
            ),
        ),
    )

    assert result.to_dict()["segments"][0]["avg_logprob"] == -0.2
    assert result.to_dict()["segments"][0]["token_ids"] == [1, 2]


def test_model_cache_respects_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert model_cache_dir() == tmp_path / "ihatemeetings" / "models"
