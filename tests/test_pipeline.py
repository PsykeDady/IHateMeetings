import json
import shutil
import wave

import pytest

from ihatemeetings.asr.base import ASRBackend, ASROptions
from ihatemeetings.config.defaults import RuntimeConfig
from ihatemeetings.models import ASRResult, ASRSegment
from ihatemeetings.pipeline.transcribe import run_transcription


class GeneratedFixtureBackend(ASRBackend):
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
            language=options.language or "it",
            language_probability=0.99,
            duration=1.0,
            duration_after_vad=None,
            segments=(ASRSegment(0.0, 0.8, "Fixture generata."),),
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
        RuntimeConfig(language="it", model=str(model_dir), device="cpu", output_dir=output_root),
        backend=GeneratedFixtureBackend(),
        emit=messages.append,
    )

    canonical = json.loads((job_dir / "transcript.json").read_text())
    raw = json.loads((job_dir / "raw" / "asr.json").read_text())
    assert canonical["segments"][0]["text"] == "Fixture generata."
    assert raw["backend"] == "generated-fixture"
    assert (job_dir / "raw" / "media.json").exists()
    assert any("Preparing audio ... done" in message for message in messages)
    assert not list(job_dir.glob(".ihm-phase1-*"))
