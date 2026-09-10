from __future__ import annotations

import importlib
import importlib.util
import platform as py_platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ToolStatus:
    name: str
    path: str | None
    version: str | None

    @property
    def installed(self) -> bool:
        return self.path is not None


@dataclass(frozen=True)
class PythonStatus:
    version: str
    supported: bool


@dataclass(frozen=True)
class PlatformInfo:
    os_name: str
    os_version: str | None
    architecture: str
    is_wsl: bool
    python: PythonStatus
    ffmpeg: ToolStatus
    ffprobe: ToolStatus
    cuda_available: bool
    gpu_name: str | None
    packages: dict[str, bool]
    cpu_compute_types: tuple[str, ...] = ()


def detect_platform() -> PlatformInfo:
    os_name, os_version = detect_os()
    gpu_name = detect_nvidia_gpu()
    return PlatformInfo(
        os_name=os_name,
        os_version=os_version,
        architecture=py_platform.machine() or "unknown",
        is_wsl=detect_wsl(),
        python=PythonStatus(
            version=".".join(str(part) for part in sys.version_info[:3]),
            supported=sys.version_info[:2] == (3, 13),
        ),
        ffmpeg=detect_tool("ffmpeg"),
        ffprobe=detect_tool("ffprobe"),
        cuda_available=gpu_name is not None,
        gpu_name=gpu_name,
        packages={
            "faster-whisper": module_usable("faster_whisper"),
            "ctranslate2": module_usable("ctranslate2"),
            "whisperx": module_available("whisperx"),
            "torch": module_available("torch"),
            "transformers": module_available("transformers"),
            "pyannote.audio": module_available("pyannote.audio"),
        },
        cpu_compute_types=detect_cpu_compute_types(),
    )


def detect_os() -> tuple[str, str | None]:
    if hasattr(py_platform, "freedesktop_os_release"):
        try:
            release = py_platform.freedesktop_os_release()
            return release.get("PRETTY_NAME") or release.get(
                "NAME"
            ) or py_platform.system(), release.get("VERSION_ID")
        except OSError:
            pass
    return py_platform.system() or "unknown", py_platform.release() or None


def detect_wsl() -> bool:
    try:
        text = Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return "microsoft" in text or "wsl" in text


def detect_tool(name: str) -> ToolStatus:
    path = shutil.which(name)
    if path is None:
        return ToolStatus(name=name, path=None, version=None)
    return ToolStatus(name=name, path=path, version=read_tool_version(path))


def read_tool_version(path: str) -> str | None:
    try:
        result = subprocess.run(
            [path, "-version"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    return first_line or None


def detect_nvidia_gpu() -> str | None:
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        return None
    try:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return names[0] if names else None


def module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


def module_usable(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
    except (ImportError, OSError, RuntimeError):
        return False
    return True


def detect_cpu_compute_types() -> tuple[str, ...]:
    try:
        import ctranslate2

        return tuple(sorted(ctranslate2.get_supported_compute_types("cpu")))
    except (ImportError, OSError, RuntimeError):
        return ()
