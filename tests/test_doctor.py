from dataclasses import replace

from ihatemeetings.platform.detect import PlatformInfo, PythonStatus, ToolStatus
from ihatemeetings.platform.doctor import is_ready_for_phase0, is_ready_for_phase1, render_doctor


def test_doctor_reports_missing_ffmpeg():
    info = PlatformInfo(
        os_name="Test Linux",
        os_version="1",
        architecture="x86_64",
        is_wsl=False,
        python=PythonStatus(version="3.13.0", supported=True),
        ffmpeg=ToolStatus(name="ffmpeg", path=None, version=None),
        ffprobe=ToolStatus(name="ffprobe", path="/usr/bin/ffprobe", version="ffprobe 1"),
        cuda_available=False,
        gpu_name=None,
        packages={
            "faster-whisper": False,
            "whisperx": False,
            "torch": False,
            "pyannote.audio": False,
        },
        cpu_compute_types=("int8",),
    )

    assert not is_ready_for_phase0(info)
    output = render_doctor(info)
    assert "FFmpeg missing" in output
    assert "sudo apt install ffmpeg" in output


def test_phase1_requires_asr_runtime():
    info = PlatformInfo(
        os_name="Test Linux",
        os_version="1",
        architecture="x86_64",
        is_wsl=False,
        python=PythonStatus(version="3.13.0", supported=True),
        ffmpeg=ToolStatus(name="ffmpeg", path="/usr/bin/ffmpeg", version="ffmpeg 1"),
        ffprobe=ToolStatus(name="ffprobe", path="/usr/bin/ffprobe", version="ffprobe 1"),
        cuda_available=False,
        gpu_name=None,
        packages={
            "faster-whisper": False,
            "ctranslate2": False,
            "whisperx": False,
            "torch": False,
            "pyannote.audio": False,
        },
        cpu_compute_types=("int8",),
    )

    assert is_ready_for_phase0(info)
    assert not is_ready_for_phase1(info)
    assert "faster-whisper missing" in render_doctor(info)

    wrong_python = replace(info, python=PythonStatus(version="3.14.0", supported=False))
    assert not is_ready_for_phase0(wrong_python)
    assert "requires the project Python 3.13 runtime" in render_doctor(wrong_python)
