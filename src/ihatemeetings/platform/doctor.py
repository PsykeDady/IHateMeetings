from __future__ import annotations

from ihatemeetings.platform.detect import PlatformInfo, detect_platform


def run_doctor() -> int:
    info = detect_platform()
    print(render_doctor(info))
    return 0 if is_ready_for_phase0(info) else 1


def is_ready_for_phase0(info: PlatformInfo) -> bool:
    return info.python.supported and info.ffmpeg.installed and info.ffprobe.installed


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
        f"- Python ............ {info.python.version} {mark(info.python.supported)}",
        f"- FFmpeg ............ {tool_label(info.ffmpeg.installed)}",
        f"- FFprobe ........... {tool_label(info.ffprobe.installed)}",
        "",
        "ML",
        f"- faster-whisper .... {optional_label(info.packages['faster-whisper'])}",
        f"- WhisperX .......... {optional_label(info.packages['whisperx'])}",
        f"- PyTorch ........... {optional_label(info.packages['torch'])}",
        f"- pyannote .......... {optional_label(info.packages['pyannote.audio'])}",
        "",
        "Hardware",
        f"- GPU ............... {info.gpu_name or 'none'}",
        f"- CUDA .............. {'available' if info.cuda_available else 'unavailable'}",
        "- CPU inference ..... available OK",
        "",
        "Optional",
        "- OCR ............... not checked in Phase 0",
        "- LLM provider ...... disabled",
    ]
    problems = remediation(info)
    if problems:
        lines.extend(["", "Problems", *problems, "", "Not ready. Fix the required items above."])
    else:
        lines.extend(["", "Ready for Phase 0."])
    return "\n".join(lines)


def remediation(info: PlatformInfo) -> list[str]:
    problems: list[str] = []
    if not info.python.supported:
        problems.append("Python 3.11 or newer is required.")
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
    return problems


def tool_label(installed: bool) -> str:
    return "OK" if installed else "missing"


def optional_label(installed: bool) -> str:
    return "installed" if installed else "not installed"


def mark(ok: bool) -> str:
    return "OK" if ok else "missing"


def yes_no(value: bool) -> str:
    return "yes" if value else "no"

