from ihatemeetings.platform.detect import PlatformInfo, PythonStatus, ToolStatus
from ihatemeetings.platform.doctor import is_ready_for_phase0, render_doctor


def test_doctor_reports_missing_ffmpeg():
    info = PlatformInfo(
        os_name="Test Linux",
        os_version="1",
        architecture="x86_64",
        is_wsl=False,
        python=PythonStatus(version="3.11.0", supported=True),
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
    )

    assert not is_ready_for_phase0(info)
    output = render_doctor(info)
    assert "FFmpeg missing" in output
    assert "sudo apt install ffmpeg" in output

