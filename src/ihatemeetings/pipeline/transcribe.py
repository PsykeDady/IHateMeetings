from __future__ import annotations

import json
import platform
import re
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from ihatemeetings import __version__
from ihatemeetings.asr import ASRBackend, ASROptions, FasterWhisperBackend
from ihatemeetings.asr.models import PROFILE_MODELS, resolve_local_model
from ihatemeetings.config.defaults import RuntimeConfig
from ihatemeetings.errors import IHMError
from ihatemeetings.exporters import export_all
from ihatemeetings.media import extract_audio, inspect_media
from ihatemeetings.models import Transcript, TranscriptSegment
from ihatemeetings.platform.compute import ComputeSelection, select_compute
from ihatemeetings.utils.time import format_timestamp

T = TypeVar("T")


@dataclass(frozen=True)
class ExecutionPlan:
    profile: str
    model: str
    language: str | None
    device: str
    compute_type: str


class ProgressReporter:
    def __init__(self, emit: Callable[[str], None] = print) -> None:
        self.emit = emit

    def run(self, stage: int, total: int, label: str, action: Callable[[], T]) -> T:
        self.emit(f"[{stage}/{total}] {label} ...")
        started = time.monotonic()
        result = action()
        self.emit(f"[{stage}/{total}] {label} ... done ({time.monotonic() - started:.1f}s)")
        return result


def build_plan(config: RuntimeConfig) -> tuple[ExecutionPlan, ComputeSelection]:
    compute = select_compute(config.device, config.compute_type)
    profile = config.profile or ("balanced" if compute.device == "cuda" else "fast")
    if profile not in PROFILE_MODELS:
        raise IHMError(f"Unknown profile '{profile}'. Choose: fast, balanced, accurate.")
    model = config.model or PROFILE_MODELS[profile]
    return ExecutionPlan(
        profile, model, config.language, compute.device, compute.compute_type
    ), compute


def run_transcription(
    source: Path,
    config: RuntimeConfig,
    *,
    backend: ASRBackend | None = None,
    emit: Callable[[str], None] = print,
) -> Path:
    reporter = ProgressReporter(emit)
    inspection = reporter.run(1, 4, "Inspecting media", lambda: inspect_media(source))
    plan, _ = build_plan(config)
    model_path = resolve_local_model(plan.model)
    job_dir = config.output_dir / _safe_job_name(source)
    raw_dir = job_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    _write_json(raw_dir / "media.json", inspection.ffprobe)

    emit("")
    emit("Execution plan")
    emit(f"Input ............ {source}")
    emit(f"Duration ......... {format_timestamp(inspection.info.duration)}")
    emit(f"Language ......... {plan.language or 'automatic detection'}")
    emit(f"Device ........... {plan.device}")
    emit(f"Compute type ..... {plan.compute_type}")
    emit("ASR .............. faster-whisper")
    emit(f"Model ............ {plan.model}")
    emit("")

    with tempfile.TemporaryDirectory(prefix=".ihm-phase1-", dir=job_dir) as temp_dir:
        audio_path = Path(temp_dir) / "audio.wav"
        reporter.run(2, 4, "Preparing audio", lambda: extract_audio(source, audio_path))
        options = ASROptions(
            model_path=model_path,
            model_name=plan.model,
            language=plan.language,
            device=plan.device,
            compute_type=plan.compute_type,
        )
        asr_result = reporter.run(
            3,
            4,
            "Transcribing",
            lambda: (backend or FasterWhisperBackend()).transcribe(audio_path, options),
        )

    _write_json(raw_dir / "asr.json", asr_result.to_dict())
    transcript = Transcript(
        duration=inspection.info.duration,
        language=asr_result.language,
        language_probability=asr_result.language_probability,
        source=source.name,
        segments=tuple(
            TranscriptSegment(
                id=f"segment-{index:06d}",
                start=segment.start,
                end=segment.end,
                text=segment.text,
            )
            for index, segment in enumerate(asr_result.segments, 1)
        ),
    )

    def write_outputs() -> object:
        outputs = export_all(transcript, job_dir)
        _write_json(
            job_dir / "metadata.json",
            {
                "ihatemeetings_version": __version__,
                "created_at": datetime.now(UTC).isoformat(),
                "platform": platform.platform(),
                "source": inspection.info.to_dict(),
                "asr": {
                    "backend": asr_result.backend,
                    "backend_version": asr_result.backend_version,
                    "model": plan.model,
                    "model_revision": _model_revision(model_path),
                    "profile": plan.profile,
                    "device": plan.device,
                    "compute_type": plan.compute_type,
                    "requested_language": plan.language,
                    "detected_language": asr_result.language,
                },
            },
        )
        return outputs

    reporter.run(4, 4, "Writing transcripts", write_outputs)
    emit(f"Output ........... {job_dir}")
    return job_dir


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _safe_job_name(source: Path) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip(".-")
    return name or "meeting"


def _model_revision(model_path: Path) -> str | None:
    return model_path.name if model_path.parent.name == "snapshots" else None
