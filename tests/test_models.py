from ihatemeetings.alignment.models import ALIGNMENT_MODELS, _model_files, alignment_cache_dir
from ihatemeetings.asr.models import model_cache_dir
from ihatemeetings.models import ASRResult, ASRSegment, Transcript, TranscriptSegment, Word


def test_canonical_transcript_is_versioned_and_typed():
    transcript = Transcript(
        duration=12.5,
        language="it",
        language_probability=0.98,
        source="meeting.wav",
        segments=(TranscriptSegment("segment-000001", 1.0, 2.5, "Buongiorno."),),
    )

    payload = transcript.to_dict()

    assert payload["schema_version"] == 2
    assert payload["meeting"]["language"] == "it"
    assert payload["speakers"] == []
    assert payload["segments"][0]["speaker"] is None
    assert payload["segments"][0]["confidence"] is None
    assert payload["segments"][0]["words"] == []


def test_aligned_word_serialization():
    word = Word("Buongiorno", 1.25, 1.83, 0.91)
    assert word.to_dict() == {
        "text": "Buongiorno",
        "start": 1.25,
        "end": 1.83,
        "confidence": 0.91,
    }


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
    assert alignment_cache_dir() == tmp_path / "ihatemeetings" / "alignment"


def test_alignment_download_selects_one_weight_format_per_model():
    english_files = _model_files(ALIGNMENT_MODELS["en"])
    italian_files = _model_files(ALIGNMENT_MODELS["it"])

    assert "model.safetensors" in english_files
    assert "pytorch_model.bin" not in english_files
    assert "pytorch_model.bin" in italian_files
    assert "model.safetensors" not in italian_files
