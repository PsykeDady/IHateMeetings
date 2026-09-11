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
from ihatemeetings.alignment import (
    AlignmentBackend,
    AlignmentOptions,
    AlignmentResult,
    CTCAlignmentBackend,
)
from ihatemeetings.alignment.models import (
    alignment_runtime_available,
    resolve_alignment_model,
)
from ihatemeetings.asr import ASRBackend, ASROptions, FasterWhisperBackend
from ihatemeetings.asr.models import PROFILE_MODELS, resolve_local_model
from ihatemeetings.config.defaults import RuntimeConfig
from ihatemeetings.diarization import (
    DiarizationBackend,
    DiarizationOptions,
    DiarizationParameters,
    DiarizationResult,
    PyannoteDiarizationBackend,
    attribute_words,
)
from ihatemeetings.diarization.models import (
    diarization_runtime_available,
    resolve_diarization_model,
)
from ihatemeetings.errors import IHMError
from ihatemeetings.exporters import export_all
from ihatemeetings.languages import (
    SUPPORTED_LANGUAGES,
    normalize_language_code,
    require_supported_language,
    unsupported_detection_warning,
)
from ihatemeetings.media import extract_audio, inspect_media
from ihatemeetings.models import ASRSegment, Speaker, Transcript, TranscriptSegment, Word
from ihatemeetings.platform.compute import ComputeSelection, select_compute
from ihatemeetings.speakers.resolution import (
    ConservativeSpeakerResolver,
    SpeakerResolver,
    apply_resolution,
)
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
    language = require_supported_language(config.language) if config.language else None
    return ExecutionPlan(profile, model, language, compute.device, compute.compute_type), compute


def run_transcription(
    source: Path,
    config: RuntimeConfig,
    *,
    backend: ASRBackend | None = None,
    alignment_backend: AlignmentBackend | None = None,
    diarization_backend: DiarizationBackend | None = None,
    speaker_resolver: SpeakerResolver | None = None,
    emit: Callable[[str], None] = print,
) -> Path:
    reporter = ProgressReporter(emit)
    inspection = reporter.run(1, 8, "Inspecting media", lambda: inspect_media(source))
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
    emit(f"Alignment ........ {_alignment_plan_label(config.align)}")
    emit(f"Diarization ...... {_diarization_plan_label(config.diarize)}")
    emit(
        "Speaker resolution "
        f"{'enabled' if config.speaker_resolution.requested else 'no evidence configured'}"
    )
    emit("")

    with tempfile.TemporaryDirectory(prefix=".ihm-phase4-", dir=job_dir) as temp_dir:
        audio_path = Path(temp_dir) / "audio.wav"
        reporter.run(2, 8, "Preparing audio", lambda: extract_audio(source, audio_path))
        options = ASROptions(
            model_path=model_path,
            model_name=plan.model,
            language=plan.language,
            device=plan.device,
            compute_type=plan.compute_type,
        )
        asr_result = reporter.run(
            3,
            8,
            "Transcribing",
            lambda: (backend or FasterWhisperBackend()).transcribe(audio_path, options),
        )
        _write_json(raw_dir / "asr.json", asr_result.to_dict())
        detected_language = normalize_language_code(asr_result.language)
        language_warning = unsupported_detection_warning(detected_language)
        supported_language = detected_language if detected_language in SUPPORTED_LANGUAGES else None
        if language_warning:
            emit(f"Language warning: {language_warning}")
        alignment_result = reporter.run(
            4,
            8,
            "Aligning words",
            lambda: _align_words(
                audio_path,
                asr_result.segments,
                supported_language,
                detected_language,
                plan.device,
                config,
                alignment_backend,
                emit,
            ),
        )
        diarization_result = reporter.run(
            5,
            8,
            "Detecting speakers",
            lambda: _diarize(
                audio_path,
                plan.device,
                config,
                diarization_backend,
                emit,
            ),
        )

    _write_json(raw_dir / "alignment.json", alignment_result.to_dict())
    _write_json(raw_dir / "diarization.json", diarization_result.to_dict())
    _write_rttm(raw_dir / "diarization.rttm", source.stem, diarization_result)
    aligned_segments = {
        segment.segment_index: segment.words for segment in alignment_result.segments
    }
    base_segments = tuple(
        TranscriptSegment(
            id=f"segment-{index:06d}",
            start=segment.start,
            end=segment.end,
            text=segment.text,
            words=aligned_segments.get(index - 1, ()),
        )
        for index, segment in enumerate(asr_result.segments, 1)
    )
    transcript = reporter.run(
        6,
        8,
        "Attributing speakers",
        lambda: _build_transcript(
            inspection.info.duration,
            detected_language,
            asr_result.language_probability,
            source.name,
            base_segments,
            diarization_result,
        ),
    )
    resolution_report = reporter.run(
        7,
        8,
        "Resolving identities",
        lambda: (speaker_resolver or ConservativeSpeakerResolver()).resolve(
            transcript, config.speaker_resolution
        ),
    )
    transcript = apply_resolution(transcript, resolution_report)

    def write_outputs() -> object:
        outputs = export_all(transcript, job_dir)
        debug_dir = job_dir / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        _write_json(
            debug_dir / "speaker_mapping.json",
            resolution_report.to_dict(),
        )
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
                    "normalized_language": detected_language,
                    "officially_supported_language": supported_language is not None,
                    "language_warning": language_warning,
                },
                "alignment": {
                    "backend": alignment_result.backend,
                    "backend_version": alignment_result.backend_version,
                    "model": alignment_result.model,
                    "language": alignment_result.language,
                    "status": alignment_result.status,
                    "warnings": list(alignment_result.warnings),
                },
                "diarization": {
                    "backend": diarization_result.backend,
                    "backend_version": diarization_result.backend_version,
                    "model": diarization_result.model,
                    "status": diarization_result.status,
                    "parameters": (
                        diarization_result.parameters.to_dict()
                        if diarization_result.parameters
                        else {}
                    ),
                    "warnings": list(diarization_result.warnings),
                },
                "speaker_resolution": {
                    "resolver": resolution_report.resolver,
                    "status": "completed" if resolution_report.requested else "not_requested",
                    "resolved_clusters": sum(
                        speaker.status == "resolved" for speaker in resolution_report.speakers
                    ),
                    "ambiguous_clusters": sum(
                        speaker.status in {"ambiguous", "conflicting"}
                        for speaker in resolution_report.speakers
                    ),
                    "warnings": list(resolution_report.warnings),
                },
            },
        )
        return outputs

    reporter.run(8, 8, "Writing transcripts", write_outputs)
    emit(f"Output ........... {job_dir}")
    return job_dir


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _write_rttm(path: Path, source_name: str, result: DiarizationResult) -> None:
    file_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", source_name).strip(".-") or "meeting"
    lines = [
        f"SPEAKER {file_id} 1 {turn.start:.3f} {turn.end - turn.start:.3f} "
        f"<NA> <NA> {turn.speaker_id} <NA> <NA>"
        for turn in result.turns
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    path.chmod(0o600)


def _safe_job_name(source: Path) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip(".-")
    return name or "meeting"


def _model_revision(model_path: Path) -> str | None:
    return model_path.name if model_path.parent.name == "snapshots" else None


def _alignment_plan_label(requested: bool | None) -> str:
    if requested is False:
        return "disabled"
    return "enabled" if requested is True else "automatic when locally available"


def _diarization_plan_label(requested: bool | None) -> str:
    if requested is False:
        return "disabled"
    return "enabled" if requested is True else "automatic when locally available"


def _align_words(
    audio_path: Path,
    segments: tuple[ASRSegment, ...],
    language: str | None,
    detected_language: str | None,
    asr_device: str,
    config: RuntimeConfig,
    backend: AlignmentBackend | None,
    emit: Callable[[str], None],
) -> AlignmentResult:
    if config.align is False:
        return AlignmentResult("none", "n/a", None, language, "disabled")
    if not language:
        if detected_language:
            reason = (
                f"detected language '{detected_language}' is not supported for v1 alignment; "
                "supported languages are it and en"
            )
            emit(f"Alignment unsupported: {reason}")
            return AlignmentResult(
                "none",
                "n/a",
                None,
                detected_language,
                "unsupported_language",
                warnings=(reason,),
            )
        return _unavailable_alignment("ASR did not provide a language", language, config, emit)
    if backend is None and not alignment_runtime_available():
        return _unavailable_alignment(
            "alignment dependencies are not installed; "
            "run 'uv sync --python 3.13 --extra alignment'",
            language,
            config,
            emit,
        )
    try:
        model_path, model_name = resolve_alignment_model(language, config.alignment_model)
        device = _alignment_device(asr_device)
        return (backend or CTCAlignmentBackend()).align(
            audio_path,
            segments,
            AlignmentOptions(model_path, model_name, language, device),
        )
    except IHMError as exc:
        detail = str(exc)
        if exc.remediation:
            detail = f"{detail} {exc.remediation}"
        return _unavailable_alignment(detail, language, config, emit)


def _unavailable_alignment(
    reason: str,
    language: str | None,
    config: RuntimeConfig,
    emit: Callable[[str], None],
) -> AlignmentResult:
    status = "unavailable" if config.align is True else "skipped"
    emit(f"Alignment {status}: {reason}")
    return AlignmentResult("none", "n/a", None, language, status, warnings=(reason,))


def _alignment_device(asr_device: str) -> str:
    if asr_device != "cuda":
        return "cpu"
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _diarize(
    audio_path: Path,
    asr_device: str,
    config: RuntimeConfig,
    backend: DiarizationBackend | None,
    emit: Callable[[str], None],
) -> DiarizationResult:
    parameters = DiarizationParameters(
        None, config.num_speakers, config.min_speakers, config.max_speakers
    )
    if config.diarize is False:
        return DiarizationResult("none", "n/a", None, "disabled", parameters=parameters)
    if backend is None and not diarization_runtime_available():
        return _unavailable_diarization(
            "diarization dependencies are not installed; run "
            "'uv sync --python 3.13 --extra diarization'",
            config,
            emit,
            parameters,
        )
    try:
        model_path, model_name = resolve_diarization_model(config.diarization_model)
        device = _alignment_device(asr_device)
        return (backend or PyannoteDiarizationBackend()).diarize(
            audio_path,
            DiarizationOptions(
                model_path,
                model_name,
                device,
                config.num_speakers,
                config.min_speakers,
                config.max_speakers,
            ),
        )
    except IHMError as exc:
        detail = str(exc)
        if exc.remediation:
            detail = f"{detail} {exc.remediation}"
        return _unavailable_diarization(detail, config, emit, parameters)


def _unavailable_diarization(
    reason: str,
    config: RuntimeConfig,
    emit: Callable[[str], None],
    parameters: DiarizationParameters,
) -> DiarizationResult:
    status = "unavailable" if config.diarize is True else "skipped"
    emit(f"Diarization {status}: {reason}")
    return DiarizationResult("none", "n/a", None, status, warnings=(reason,), parameters=parameters)


def _build_transcript(
    duration: float,
    language: str | None,
    language_probability: float | None,
    source: str,
    segments: tuple[TranscriptSegment, ...],
    diarization: DiarizationResult,
) -> Transcript:
    if diarization.status != "completed":
        return Transcript(duration, language, language_probability, source, segments)
    attributed = tuple(
        TranscriptSegment(
            segment.id,
            segment.start,
            segment.end,
            segment.text,
            attribute_words(segment.words, diarization.turns),
        )
        for segment in segments
    )
    rebuilt = _reconstruct_speaker_turns(attributed)
    speaker_ids = sorted({turn.speaker_id for turn in diarization.turns})
    return Transcript(
        duration,
        language,
        language_probability,
        source,
        rebuilt,
        tuple(Speaker(speaker_id) for speaker_id in speaker_ids),
    )


def _reconstruct_speaker_turns(
    segments: tuple[TranscriptSegment, ...],
) -> tuple[TranscriptSegment, ...]:
    rebuilt: list[TranscriptSegment] = []
    for source_segment in segments:
        words = source_segment.words
        if not words or " ".join(word.text for word in words) != source_segment.text:
            assignments = [word.speaker.speaker_id if word.speaker else None for word in words]
            speaker_ids = set(assignments)
            speaker = (
                Speaker(assignments[0])
                if assignments and None not in speaker_ids and len(speaker_ids) == 1
                else None
            )
            rebuilt.append(
                TranscriptSegment(
                    "",
                    source_segment.start,
                    source_segment.end,
                    source_segment.text,
                    words,
                    speaker,
                )
            )
            continue
        runs: list[list[Word]] = []
        for word in words:
            speaker_id = word.speaker.speaker_id if word.speaker else None
            previous_id = runs[-1][-1].speaker.speaker_id if runs and runs[-1][-1].speaker else None
            if not runs or previous_id != speaker_id:
                runs.append([])
            runs[-1].append(word)
        for run in runs:
            speaker_id = run[0].speaker.speaker_id if run[0].speaker else None
            rebuilt.append(
                TranscriptSegment(
                    "",
                    run[0].start if run[0].start is not None else source_segment.start,
                    run[-1].end if run[-1].end is not None else source_segment.end,
                    " ".join(word.text for word in run),
                    tuple(run),
                    Speaker(speaker_id) if speaker_id else None,
                )
            )
    merged: list[TranscriptSegment] = []
    for segment in rebuilt:
        if (
            merged
            and segment.speaker is not None
            and merged[-1].speaker == segment.speaker
            and segment.start - merged[-1].end <= 1.0
        ):
            previous = merged.pop()
            merged.append(
                TranscriptSegment(
                    "",
                    previous.start,
                    segment.end,
                    f"{previous.text} {segment.text}",
                    (*previous.words, *segment.words),
                    segment.speaker,
                )
            )
        else:
            merged.append(segment)
    return tuple(
        TranscriptSegment(
            f"segment-{index:06d}",
            segment.start,
            segment.end,
            segment.text,
            segment.words,
            segment.speaker,
        )
        for index, segment in enumerate(merged, 1)
    )
