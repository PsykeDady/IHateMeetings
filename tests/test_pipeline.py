import json
import shutil
import wave

import pytest

from ihatemeetings.alignment import (
    AlignmentBackend,
    AlignmentOptions,
    AlignmentResult,
    AlignmentSegment,
)
from ihatemeetings.asr.base import ASRBackend, ASROptions
from ihatemeetings.config.defaults import RuntimeConfig
from ihatemeetings.models import ASRResult, ASRSegment, Word
from ihatemeetings.pipeline.transcribe import run_transcription


class GeneratedFixtureBackend(ASRBackend):
    def __init__(self, detected_language="it"):
        self.detected_language = detected_language

    def transcribe(self, audio_path, options: ASROptions) -> ASRResult:
        assert audio_path.exists()
        with wave.open(str(audio_path), "rb") as audio:
            assert audio.getframerate() == 16000
            assert audio.getnchannels() == 1
            assert audio.getsampwidth() == 2
        return ASRResult(
            backend="generated-fixture",
            backend_version="1",
            model=options.model_name,
            language=options.language or self.detected_language,
            language_probability=0.99,
            duration=1.0,
            duration_after_vad=None,
            segments=(ASRSegment(0.0, 0.8, "Fixture generata."),),
        )


class GeneratedAlignmentBackend(AlignmentBackend):
    def align(self, audio_path, segments, options: AlignmentOptions) -> AlignmentResult:
        assert options.device == "cpu"
        return AlignmentResult(
            backend="generated-alignment",
            backend_version="1",
            model=options.model_name,
            language=options.language,
            status="completed",
            segments=(
                AlignmentSegment(
                    segment_index=0,
                    start=0.0,
                    end=0.8,
                    text=segments[0].text,
                    words=(
                        Word("Fixture", 0.0, 0.4, 0.9),
                        Word("generata.", 0.45, 0.8, 0.85),
                    ),
                ),
            ),
        )


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg integration tools are unavailable",
)
def test_generated_audio_runs_through_real_media_pipeline(tmp_path):
    source = tmp_path / "generated.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 2 * 8000)
    model_dir = tmp_path / "local-model"
    model_dir.mkdir()
    output_root = tmp_path / "output"
    messages = []

    job_dir = run_transcription(
        source,
        RuntimeConfig(
            language="it",
            model=str(model_dir),
            device="cpu",
            align=False,
            output_dir=output_root,
        ),
        backend=GeneratedFixtureBackend(),
        emit=messages.append,
    )

    canonical = json.loads((job_dir / "transcript.json").read_text())
    raw = json.loads((job_dir / "raw" / "asr.json").read_text())
    alignment = json.loads((job_dir / "raw" / "alignment.json").read_text())
    assert canonical["segments"][0]["text"] == "Fixture generata."
    assert raw["backend"] == "generated-fixture"
    assert alignment["status"] == "disabled"
    assert canonical["segments"][0]["words"] == []
    assert (job_dir / "raw" / "media.json").exists()
    assert any("Preparing audio ... done" in message for message in messages)
    assert not list(job_dir.glob(".ihm-phase2-*"))


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg integration tools are unavailable",
)
def test_pipeline_serializes_alignment_without_mutating_raw_asr(tmp_path):
    source = tmp_path / "aligned.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 16000)
    model_dir = tmp_path / "local-model"
    model_dir.mkdir()

    job_dir = run_transcription(
        source,
        RuntimeConfig(
            language="it",
            model=str(model_dir),
            device="cpu",
            align=True,
            alignment_model=str(model_dir),
            output_dir=tmp_path / "output",
        ),
        backend=GeneratedFixtureBackend(),
        alignment_backend=GeneratedAlignmentBackend(),
        emit=lambda _message: None,
    )

    raw_asr = json.loads((job_dir / "raw" / "asr.json").read_text())
    raw_alignment = json.loads((job_dir / "raw" / "alignment.json").read_text())
    canonical = json.loads((job_dir / "transcript.json").read_text())
    assert "words" not in raw_asr["segments"][0]
    assert raw_alignment["status"] == "completed"
    assert canonical["segments"][0]["words"][0]["text"] == "Fixture"


@pytest.mark.parametrize("detected_language", ("it", "en"))
def test_automatic_supported_language_routes_alignment(detected_language, tmp_path):
    source = tmp_path / f"automatic-{detected_language}.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 16000)
    model_dir = tmp_path / "local-model"
    model_dir.mkdir()

    job_dir = run_transcription(
        source,
        RuntimeConfig(
            model=str(model_dir),
            device="cpu",
            align=True,
            alignment_model=str(model_dir),
            output_dir=tmp_path / "output",
        ),
        backend=GeneratedFixtureBackend(detected_language),
        alignment_backend=GeneratedAlignmentBackend(),
        emit=lambda _message: None,
    )

    alignment = json.loads((job_dir / "raw" / "alignment.json").read_text())
    metadata = json.loads((job_dir / "metadata.json").read_text())
    assert alignment["language"] == detected_language
    assert alignment["status"] == "completed"
    assert metadata["asr"]["officially_supported_language"] is True


def test_automatic_unsupported_language_warns_and_preserves_asr(tmp_path):
    source = tmp_path / "unsupported.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 16000)
    model_dir = tmp_path / "local-model"
    model_dir.mkdir()
    messages = []

    job_dir = run_transcription(
        source,
        RuntimeConfig(model=str(model_dir), device="cpu", output_dir=tmp_path / "output"),
        backend=GeneratedFixtureBackend("fr"),
        alignment_backend=GeneratedAlignmentBackend(),
        emit=messages.append,
    )

    transcript = json.loads((job_dir / "transcript.json").read_text())
    alignment = json.loads((job_dir / "raw" / "alignment.json").read_text())
    metadata = json.loads((job_dir / "metadata.json").read_text())
    assert transcript["meeting"]["language"] == "fr"
    assert transcript["segments"][0]["text"] == "Fixture generata."
    assert alignment["status"] == "unsupported_language"
    assert metadata["asr"]["officially_supported_language"] is False
    assert any("Language warning" in message for message in messages)
