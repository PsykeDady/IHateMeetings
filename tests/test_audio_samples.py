from __future__ import annotations

import hashlib
import json
import os
import time
import unicodedata
import wave
from difflib import SequenceMatcher
from pathlib import Path

import pytest

from ihatemeetings.alignment.models import is_alignment_model_cached
from ihatemeetings.asr.models import is_model_cached
from ihatemeetings.config.defaults import RuntimeConfig
from ihatemeetings.diarization import DiarizationOptions, PyannoteDiarizationBackend
from ihatemeetings.diarization.models import (
    is_diarization_model_cached,
    resolve_diarization_model,
)
from ihatemeetings.metrics import character_error_rate, word_error_rate
from ihatemeetings.pipeline import run_transcription

FIXTURE_DIR = Path(__file__).parent / "private_audio"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"
MANIFEST = (
    json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
)


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
            align=False,
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
    print(
        f"{filename}: WER={word_error_rate(expected['text'], recognized):.4f} "
        f"CER={character_error_rate(expected['text'], recognized):.4f}"
    )


@pytest.mark.real_alignment
@pytest.mark.parametrize("filename", tuple(MANIFEST))
def test_real_cpu_alignment_on_private_italian_samples(filename, tmp_path):
    if os.environ.get("IHM_RUN_REAL_ALIGNMENT") != "1":
        pytest.skip("set IHM_RUN_REAL_ALIGNMENT=1 to enable local word alignment")
    model = os.environ.get("IHM_TEST_MODEL", "tiny")
    if not is_model_cached(model):
        pytest.skip(f"model '{model}' is not cached; run 'ihm models download {model}'")
    if not is_alignment_model_cached("it"):
        pytest.skip("Italian alignment model is not cached; download it explicitly")

    job_dir = run_transcription(
        FIXTURE_DIR / filename,
        RuntimeConfig(
            language="it",
            model=model,
            device="cpu",
            compute_type="int8",
            align=True,
            output_dir=tmp_path,
        ),
        emit=lambda _message: None,
    )
    transcript = json.loads((job_dir / "transcript.json").read_text(encoding="utf-8"))
    alignment = json.loads((job_dir / "raw" / "alignment.json").read_text(encoding="utf-8"))
    raw_asr = json.loads((job_dir / "raw" / "asr.json").read_text(encoding="utf-8"))

    assert alignment["status"] in {"completed", "partial"}
    aligned_words = [
        word
        for segment in transcript["segments"]
        for word in segment["words"]
        if word["start"] is not None
    ]
    assert aligned_words
    duration = transcript["meeting"]["duration"]
    for segment in transcript["segments"]:
        previous_start = segment["start"]
        for word in segment["words"]:
            if word["start"] is None:
                continue
            assert segment["start"] <= word["start"] <= word["end"] <= segment["end"]
            assert word["end"] <= duration
            assert word["start"] >= previous_start
            previous_start = word["start"]

    recognized = " ".join(segment["text"] for segment in transcript["segments"])
    raw_recognized = " ".join(segment["text"] for segment in raw_asr["segments"])
    assert recognized == raw_recognized
    expected = MANIFEST[filename]
    normalized_recognized = _normalize(recognized)
    matches = sum(
        _has_keyword(normalized_recognized, keyword) for keyword in expected["keywords"]
    )
    assert matches >= expected["minimum_keyword_matches"], normalized_recognized
    print(
        f"{filename} aligned: "
        f"WER={word_error_rate(expected['text'], normalized_recognized):.4f} "
        f"CER={character_error_rate(expected['text'], normalized_recognized):.4f}"
    )


@pytest.mark.real_diarization
@pytest.mark.parametrize("filename", tuple(MANIFEST)[:1])
def test_real_pyannote_cpu_diarization_on_private_sample(filename):
    if os.environ.get("IHM_RUN_REAL_DIARIZATION") != "1":
        pytest.skip("set IHM_RUN_REAL_DIARIZATION=1 to enable local pyannote inference")
    if not is_diarization_model_cached():
        pytest.skip("Community-1 is not prepared; run 'ihm models download-diarization'")
    model_path, model_name = resolve_diarization_model()
    audio_path = FIXTURE_DIR / filename
    started = time.monotonic()
    result = PyannoteDiarizationBackend().diarize(
        audio_path,
        DiarizationOptions(model_path, model_name, "cpu"),
    )
    elapsed = time.monotonic() - started

    assert result.status == "completed"
    assert result.turns
    duration = MANIFEST[filename]["duration"]
    assert all(0 <= turn.start <= turn.end <= duration + 0.25 for turn in result.turns)
    assert all(
        current.start <= following.start
        for current, following in zip(result.turns, result.turns[1:])
    )
    speakers = {turn.speaker_id for turn in result.turns}
    print(
        f"{filename}: audio={duration:.2f}s diarization={elapsed:.2f}s "
        f"speakers={len(speakers)} turns={len(result.turns)}"
    )


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
