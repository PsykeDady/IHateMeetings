from __future__ import annotations

from ihatemeetings.alignment.models import (
    ALIGNMENT_MODELS,
    alignment_runtime_available,
    is_alignment_model_cached,
)
from ihatemeetings.asr.models import MODELS, is_model_cached
from ihatemeetings.diarization.models import (
    COMMUNITY_1,
    diarization_runtime_available,
    is_diarization_model_cached,
)
from ihatemeetings.platform.compute import cuda_device_count
from ihatemeetings.platform.detect import PlatformInfo, detect_platform


def run_doctor() -> int:
    info = detect_platform()
    print(render_doctor(info))
    return 0 if is_ready_for_phase1(info) else 1


def is_ready_for_phase0(info: PlatformInfo) -> bool:
    return info.python.supported and info.ffmpeg.installed and info.ffprobe.installed


def is_ready_for_phase1(info: PlatformInfo) -> bool:
    return (
        is_ready_for_phase0(info)
        and info.packages.get("faster-whisper", False)
        and info.packages.get("ctranslate2", False)
        and "int8" in info.cpu_compute_types
    )


def render_doctor(info: PlatformInfo) -> str:
    lines = [
        "IHateMeetings Doctor",
        "",
        "Platform",
        f"- OS ................ {info.os_name}",
        f"- Architecture ...... {info.architecture}",
        f"- WSL ............... {yes_no(info.is_wsl)}",
        "",
        "Runtime",
        "- Python target ...... 3.13 (project runtime managed by uv)",
        f"- Python ............ {info.python.version} {mark(info.python.supported)}",
        f"- FFmpeg ............ {tool_label(info.ffmpeg.installed)}",
        f"- FFprobe ........... {tool_label(info.ffprobe.installed)}",
        "",
        "ML",
        f"- faster-whisper .... {required_label(info.packages.get('faster-whisper', False))}",
        f"- CTranslate2 ....... {required_label(info.packages.get('ctranslate2', False))}",
        f"- WhisperX .......... {optional_label(info.packages['whisperx'])} (not required)",
        f"- PyTorch ........... {optional_label(info.packages['torch'])}",
        f"- pyannote .......... {optional_label(info.packages['pyannote.audio'])}",
        "",
        "Hardware",
        f"- GPU ............... {info.gpu_name or 'none'}",
        f"- CUDA .............. {cuda_label(info)}",
        f"- CPU INT8 .......... {required_label('int8' in info.cpu_compute_types)}",
        "",
        "Models",
        "- Languages ......... it, en (official v1 support)",
        f"- Cached ............ {cached_model_label()}",
        f"- Transcription ..... {transcription_label(info)}",
        "",
        "Alignment",
        f"- Torch ............. {optional_label(info.packages.get('torch', False))}",
        f"- Transformers ...... {optional_label(info.packages.get('transformers', False))}",
        f"- Runtime ........... {alignment_runtime_label()}",
        f"- Cached models ..... {cached_alignment_model_label()}",
        f"- Status ............ {alignment_status_label()}",
        "",
        "Diarization",
        f"- pyannote.audio ..... {optional_label(info.packages['pyannote.audio'])}",
        f"- Runtime ........... {diarization_runtime_label()}",
        f"- Model ............. {diarization_model_label()}",
        f"- Status ............ {diarization_status_label()}",
        "",
        "Optional",
        "- OCR ............... not installed (future phase)",
        "- LLM provider ...... disabled",
    ]
    problems = remediation(info)
    if problems:
        lines.extend(["", "Problems", *problems, "", "Not ready. Fix the required items above."])
    else:
        lines.extend(
            [
                "",
                "Basic transcription runtime ready.",
            ]
        )
    return "\n".join(lines)


def remediation(info: PlatformInfo) -> list[str]:
    problems: list[str] = []
    if not info.python.supported:
        problems.extend(
            [
                "IHateMeetings requires the project Python 3.13 runtime.",
                "  Run: uv python install 3.13",
                "  Then: uv sync --python 3.13 --extra dev --extra alignment",
            ]
        )
    if not info.ffmpeg.installed:
        problems.extend(
            [
                "FFmpeg missing.",
                "  Arch:   sudo pacman -S --needed ffmpeg",
                "  Ubuntu: sudo apt install ffmpeg",
                "  Fedora: sudo dnf install ffmpeg",
            ]
        )
    if not info.ffprobe.installed:
        problems.append("FFprobe missing. It is usually provided by the FFmpeg package.")
    if not info.packages.get("faster-whisper", False):
        problems.append("faster-whisper missing. Run: uv sync --python 3.13 --extra dev")
    if not info.packages.get("ctranslate2", False):
        problems.append("CTranslate2 missing. Run: uv sync --python 3.13 --extra dev")
    elif "int8" not in info.cpu_compute_types:
        problems.append("CTranslate2 CPU INT8 inference is unavailable on this machine.")
    return problems


def tool_label(installed: bool) -> str:
    return "OK" if installed else "missing"


def optional_label(installed: bool) -> str:
    return "installed" if installed else "not installed"


def required_label(installed: bool) -> str:
    return "OK" if installed else "missing"


def cuda_label(info: PlatformInfo) -> str:
    if not info.cuda_available:
        return "unavailable (CPU INT8 selected)"
    count = cuda_device_count()
    return (
        f"available ({count} CTranslate2 device(s))" if count else "GPU found; runtime unavailable"
    )


def cached_models() -> tuple[str, ...]:
    return tuple(name for name in MODELS if is_model_cached(name))


def cached_model_label() -> str:
    available = cached_models()
    return ", ".join(available) if available else "none"


def transcription_label(info: PlatformInfo) -> str:
    if not is_ready_for_phase1(info):
        return "runtime unavailable"
    if not cached_models():
        return "model required; run 'ihm models download small'"
    return "operational OK"


def cached_alignment_models() -> tuple[str, ...]:
    return tuple(language for language in ALIGNMENT_MODELS if is_alignment_model_cached(language))


def cached_alignment_model_label() -> str:
    available = cached_alignment_models()
    return ", ".join(available) if available else "none"


def alignment_runtime_label() -> str:
    return (
        "OK"
        if alignment_runtime_available(verify_imports=True)
        else "not installed or unusable (optional)"
    )


def alignment_status_label() -> str:
    if not alignment_runtime_available(verify_imports=True):
        return "unavailable; run 'uv sync --python 3.13 --extra alignment'"
    if not cached_alignment_models():
        return "model required; run 'ihm models download-alignment it'"
    return "operational OK"


def diarization_runtime_label() -> str:
    return (
        "OK (CPU supported)"
        if diarization_runtime_available(verify_imports=True)
        else "not installed or unusable (optional)"
    )


def diarization_model_label() -> str:
    if is_diarization_model_cached():
        return f"{COMMUNITY_1.name} cached"
    return f"{COMMUNITY_1.name} not prepared (gated, {COMMUNITY_1.license})"


def diarization_status_label() -> str:
    if not diarization_runtime_available(verify_imports=True):
        return "unavailable; run 'uv sync --python 3.13 --extra diarization'"
    if not is_diarization_model_cached():
        return "model required; run 'ihm models download-diarization' with HF_TOKEN"
    return "operational OK (local/offline inference)"


def mark(ok: bool) -> str:
    return "OK" if ok else "missing"


def yes_no(value: bool) -> str:
    return "yes" if value else "no"
