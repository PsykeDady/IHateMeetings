from __future__ import annotations

import os
import wave
from array import array
from importlib.metadata import version
from pathlib import Path

from ihatemeetings.diarization.base import (
    DiarizationBackend,
    DiarizationOptions,
    DiarizationParameters,
    DiarizationResult,
    DiarizationTurn,
)
from ihatemeetings.diarization.models import diarization_cache_dir
from ihatemeetings.errors import IHMError


class PyannoteDiarizationBackend(DiarizationBackend):
    def diarize(self, audio_path: Path, options: DiarizationOptions) -> DiarizationResult:
        # No telemetry and no Hub access are permitted during normal meeting processing.
        os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
        os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            import torch
            from pyannote.audio import Pipeline

            pipeline = Pipeline.from_pretrained(
                options.model_path, cache_dir=diarization_cache_dir()
            )
            if pipeline is None:
                raise IHMError("pyannote could not load the prepared local pipeline.")
            pipeline.to(torch.device(options.device))
            waveform, sample_rate = _read_pcm_wave(audio_path, torch)
            parameters = {
                key: value
                for key, value in {
                    "num_speakers": options.num_speakers,
                    "min_speakers": options.min_speakers,
                    "max_speakers": options.max_speakers,
                }.items()
                if value is not None
            }
            output = pipeline(
                {"waveform": waveform, "sample_rate": sample_rate},
                **parameters,
            )
            annotation = output.speaker_diarization
        except Exception as exc:
            raise IHMError(
                f"Local pyannote diarization failed: {exc}",
                "Run 'ihm doctor'; verify the local Community-1 setup and CPU/GPU runtime.",
            ) from exc

        labels: dict[str, str] = {}
        turns: list[DiarizationTurn] = []
        for segment, _, label in annotation.itertracks(yield_label=True):
            normalized = labels.setdefault(str(label), f"SPEAKER_{len(labels):02d}")
            turns.append(DiarizationTurn(normalized, float(segment.start), float(segment.end)))
        turns.sort(key=lambda turn: (turn.start, turn.end, turn.speaker_id))
        return DiarizationResult(
            backend="pyannote.audio",
            backend_version=version("pyannote-audio"),
            model=options.model_name,
            status="completed",
            turns=tuple(turns),
            parameters=DiarizationParameters(
                options.device,
                options.num_speakers,
                options.min_speakers,
                options.max_speakers,
            ),
        )


def _read_pcm_wave(audio_path: Path, torch: object) -> tuple[object, int]:
    with wave.open(str(audio_path), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
            raise IHMError("Diarization requires the internal mono PCM16 audio representation.")
        sample_rate = audio.getframerate()
        samples = array("h")
        samples.frombytes(audio.readframes(audio.getnframes()))
    waveform = torch.tensor(samples, dtype=torch.float32).div_(32768.0).unsqueeze(0)
    return waveform, sample_rate
