from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from ihatemeetings.asr.base import ASRBackend, ASROptions
from ihatemeetings.errors import IHMError
from ihatemeetings.models import ASRResult, ASRSegment


class FasterWhisperBackend(ASRBackend):
    def transcribe(self, audio_path: Path, options: ASROptions) -> ASRResult:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise IHMError(
                "faster-whisper is not installed.",
                "Run 'uv sync --extra dev' and then 'uv run ihm doctor'.",
            ) from exc

        try:
            model = WhisperModel(
                str(options.model_path),
                device=options.device,
                compute_type=options.compute_type,
            )
            generated_segments, info = model.transcribe(
                str(audio_path),
                language=options.language,
                beam_size=5,
                vad_filter=False,
                word_timestamps=False,
            )
            segments = tuple(
                ASRSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=str(segment.text).strip(),
                    token_ids=tuple(int(token) for token in getattr(segment, "tokens", ())),
                    avg_logprob=_optional_float(getattr(segment, "avg_logprob", None)),
                    no_speech_prob=_optional_float(getattr(segment, "no_speech_prob", None)),
                    compression_ratio=_optional_float(getattr(segment, "compression_ratio", None)),
                    temperature=_optional_float(getattr(segment, "temperature", None)),
                )
                for segment in generated_segments
                if str(segment.text).strip()
            )
        except (OSError, RuntimeError, ValueError) as exc:
            hint = (
                "Try '--device cpu --compute-type int8'. For CUDA, verify the CTranslate2 "
                "CUDA/cuDNN requirements shown by 'ihm doctor'."
            )
            raise IHMError(f"faster-whisper inference failed: {exc}", hint) from exc

        try:
            backend_version = version("faster-whisper")
        except PackageNotFoundError:
            backend_version = "unknown"
        return ASRResult(
            backend="faster-whisper",
            backend_version=backend_version,
            model=options.model_name,
            language=getattr(info, "language", options.language),
            language_probability=_optional_float(getattr(info, "language_probability", None)),
            duration=float(getattr(info, "duration", 0.0)),
            duration_after_vad=_optional_float(getattr(info, "duration_after_vad", None)),
            segments=segments,
        )


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None
