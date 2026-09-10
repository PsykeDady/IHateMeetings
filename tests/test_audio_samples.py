from __future__ import annotations

import hashlib
import json
import os
import unicodedata
import wave
from difflib import SequenceMatcher
from pathlib import Path

import pytest

from ihatemeetings.asr.models import is_model_cached
from ihatemeetings.config.defaults import RuntimeConfig
from ihatemeetings.pipeline import run_transcription

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "audio"
MANIFEST = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("filename", tuple(MANIFEST))
def test_italian_audio_fixture_integrity(filename):
    expected = MANIFEST[filename]
    audio_path = FIXTURE_DIR / filename

    assert hashlib.sha256(audio_path.read_bytes()).hexdigest() == expected["sha256"]
    with wave.open(str(audio_path), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 16000
        assert audio.getnframes() / audio.getframerate() == pytest.approx(
            expected["duration"], abs=0.01
        )


@pytest.mark.real_asr
@pytest.mark.parametrize("filename", tuple(MANIFEST))
def test_real_faster_whisper_italian_samples(filename, tmp_path):
    if os.environ.get("IHM_RUN_REAL_ASR") != "1":
        pytest.skip("set IHM_RUN_REAL_ASR=1 to enable local model inference")
    model = os.environ.get("IHM_TEST_MODEL", "tiny")
    if not is_model_cached(model):
        pytest.skip(f"model '{model}' is not cached; run 'ihm models download {model}'")

    job_dir = run_transcription(
        FIXTURE_DIR / filename,
        RuntimeConfig(
            language="it",
            model=model,
            device="cpu",
            compute_type="int8",
            output_dir=tmp_path,
        ),
        emit=lambda _message: None,
    )
    transcript = json.loads((job_dir / "transcript.json").read_text(encoding="utf-8"))
    recognized = _normalize(" ".join(segment["text"] for segment in transcript["segments"]))

    assert transcript["meeting"]["language"] == "it"
    assert recognized
    expected = MANIFEST[filename]
    matches = sum(_has_keyword(recognized, keyword) for keyword in expected["keywords"])
    assert matches >= expected["minimum_keyword_matches"], recognized


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(
        "".join(character if character.isalnum() else " " for character in decomposed).split()
    )


def _has_keyword(recognized: str, keyword: str) -> bool:
    expected = _normalize(keyword)
    return any(
        token == expected or SequenceMatcher(None, token, expected).ratio() >= 0.75
        for token in recognized.split()
    )
