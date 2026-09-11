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
from ihatemeetings.diarization import (
    DiarizationBackend,
    DiarizationOptions,
    DiarizationParameters,
    DiarizationResult,
    DiarizationTurn,
)
from ihatemeetings.models import ASRResult, ASRSegment, SpeakerIdentity, Word
from ihatemeetings.pipeline.transcribe import run_transcription
from ihatemeetings.speakers import ManualSpeakerMapping, ResolutionConfig


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


class GeneratedDiarizationBackend(DiarizationBackend):
    def diarize(self, audio_path, options: DiarizationOptions) -> DiarizationResult:
        assert audio_path.exists()
        assert options.device == "cpu"
        return DiarizationResult(
            "generated-diarization",
            "1",
            options.model_name,
            "completed",
            (
                DiarizationTurn("SPEAKER_00", 0.0, 0.42),
                DiarizationTurn("SPEAKER_01", 0.42, 0.8),
            ),
            parameters=DiarizationParameters(device=options.device),
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
            diarize=False,
            output_dir=output_root,
        ),
        backend=GeneratedFixtureBackend(),
        emit=messages.append,
    )

    canonical = json.loads((job_dir / "transcript.json").read_text())
    raw = json.loads((job_dir / "raw" / "asr.json").read_text())
    alignment = json.loads((job_dir / "raw" / "alignment.json").read_text())
    assert canonical["segments"][0]["text"] == "Fixture generata."
    assert canonical["segments"][0]["id"] == "SEG_000001"
    assert canonical["segments"][0]["unknown_id"] == "UNK_000001"
    assert raw["backend"] == "generated-fixture"
    assert alignment["status"] == "disabled"
    diarization = json.loads((job_dir / "raw" / "diarization.json").read_text())
    assert diarization["status"] == "disabled"
    assert (job_dir / "raw" / "diarization.rttm").read_text() == ""
    assert canonical["segments"][0]["words"] == []
    assert (job_dir / "raw" / "media.json").exists()
    assert any("Preparing audio ... done" in message for message in messages)
    assert not list(job_dir.glob(".ihm-phase4-*"))


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


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg integration tools are unavailable",
)
def test_pipeline_writes_diarization_artifacts_and_schema_v5(tmp_path):
    source = tmp_path / "speakers.wav"
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
            diarize=True,
            diarization_model=str(model_dir),
            output_dir=tmp_path / "output",
        ),
        backend=GeneratedFixtureBackend(),
        alignment_backend=GeneratedAlignmentBackend(),
        diarization_backend=GeneratedDiarizationBackend(),
        emit=lambda _message: None,
    )

    raw_asr = json.loads((job_dir / "raw" / "asr.json").read_text())
    raw_alignment = json.loads((job_dir / "raw" / "alignment.json").read_text())
    raw_diarization = json.loads((job_dir / "raw" / "diarization.json").read_text())
    canonical = json.loads((job_dir / "transcript.json").read_text())
    assert "words" not in raw_asr["segments"][0]
    assert "speaker" not in raw_alignment["segments"][0]["words"][0]
    assert raw_diarization["backend"] == "generated-diarization"
    assert "SPEAKER speakers 1 0.000 0.420" in (job_dir / "raw" / "diarization.rttm").read_text()
    assert canonical["schema_version"] == 5
    assert [segment["id"] for segment in canonical["segments"]] == [
        "SEG_000001",
        "SEG_000002",
    ]
    assert all(segment["unknown_id"] is None for segment in canonical["segments"])
    assert [speaker["cluster"] for speaker in canonical["speakers"]] == [
        "SPEAKER_00",
        "SPEAKER_01",
    ]
    assert [segment["speaker"]["cluster"] for segment in canonical["segments"]] == [
        "SPEAKER_00",
        "SPEAKER_01",
    ]


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg integration tools are unavailable",
)
def test_pipeline_applies_manual_mapping_without_mutating_raw_diarization(tmp_path):
    source = tmp_path / "mapped.wav"
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
            diarize=True,
            diarization_model=str(model_dir),
            speaker_resolution=ResolutionConfig(
                manual_mappings=(
                    ManualSpeakerMapping(
                        "SPEAKER_00",
                        SpeakerIdentity("participant-a", "Partecipante A"),
                    ),
                )
            ),
            output_dir=tmp_path / "output",
        ),
        backend=GeneratedFixtureBackend(),
        alignment_backend=GeneratedAlignmentBackend(),
        diarization_backend=GeneratedDiarizationBackend(),
        emit=lambda _message: None,
    )

    raw = json.loads((job_dir / "raw" / "diarization.json").read_text())
    canonical = json.loads((job_dir / "transcript.json").read_text())
    audit = json.loads((job_dir / "debug" / "speaker_mapping.json").read_text())
    assert "name" not in raw["turns"][0]
    speaker = canonical["speakers"][0]
    assert speaker["cluster"] == "SPEAKER_00"
    assert speaker["identity"] == {
        "id": "participant-a",
        "display_name": "Partecipante A",
    }
    assert speaker["resolution"]["confidence"] == 1.0
    assert speaker["resolution"]["evidence"][0]["type"] == "manual_mapping"
    assert canonical["segments"][0]["speaker"] == speaker
    assert audit["clusters"][0] == speaker


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg integration tools are unavailable",
)
def test_no_identity_configuration_preserves_anonymous_and_unknown_speakers(tmp_path):
    source = tmp_path / "anonymous.wav"
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
            diarize=True,
            diarization_model=str(model_dir),
            output_dir=tmp_path / "output",
        ),
        backend=GeneratedFixtureBackend(),
        alignment_backend=GeneratedAlignmentBackend(),
        diarization_backend=GeneratedDiarizationBackend(),
        emit=lambda _message: None,
    )

    canonical = json.loads((job_dir / "transcript.json").read_text())
    audit = json.loads((job_dir / "debug" / "speaker_mapping.json").read_text())
    assert [speaker["identity"] for speaker in canonical["speakers"]] == [None, None]
    assert [speaker["resolution"]["status"] for speaker in canonical["speakers"]] == [
        "unresolved",
        "unresolved",
    ]
    assert audit["requested"] is False
