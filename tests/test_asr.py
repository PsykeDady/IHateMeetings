from types import SimpleNamespace

import faster_whisper

from ihatemeetings.asr.base import ASROptions
from ihatemeetings.asr.faster_whisper import FasterWhisperBackend


def test_faster_whisper_backend_converts_and_consumes_segments(monkeypatch, tmp_path):
    created = {}

    class FakeWhisperModel:
        def __init__(self, model_path, **kwargs):
            created["model_path"] = model_path
            created["init"] = kwargs

        def transcribe(self, audio_path, **kwargs):
            created["audio_path"] = audio_path
            created["transcribe"] = kwargs
            segments = iter(
                [
                    SimpleNamespace(
                        start=0.1, end=1.2, text=" Ciao ", avg_logprob=-0.1, no_speech_prob=0.02
                    )
                ]
            )
            info = SimpleNamespace(
                language="it", language_probability=0.97, duration=1.5, duration_after_vad=1.5
            )
            return segments, info

    monkeypatch.setattr(faster_whisper, "WhisperModel", FakeWhisperModel)
    audio = tmp_path / "audio.wav"
    model = tmp_path / "model"
    result = FasterWhisperBackend().transcribe(
        audio,
        ASROptions(
            model,
            "tiny",
            "it",
            "cpu",
            "int8",
            glossary_terms=("DynamoDB", "API Gateway", "STAG"),
        ),
    )

    assert result.segments[0].text == "Ciao"
    assert result.language == "it"
    assert created["init"] == {"device": "cpu", "compute_type": "int8"}
    assert created["transcribe"]["word_timestamps"] is False
    assert created["transcribe"]["task"] == "transcribe"
    assert created["transcribe"]["initial_prompt"] == "DynamoDB, API Gateway, STAG"
