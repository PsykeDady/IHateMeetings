import json
import subprocess

import pytest

from ihatemeetings.errors import IHMError
from ihatemeetings.media.ffmpeg import inspect_media


def test_ffprobe_metadata_is_converted_to_typed_model(monkeypatch, tmp_path):
    source = tmp_path / "meeting.mp4"
    source.touch()
    payload = {
        "format": {"duration": "12.25", "format_name": "mov,mp4", "size": "42"},
        "streams": [{"codec_type": "audio"}, {"codec_type": "video"}],
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, json.dumps(payload), ""),
    )

    inspection = inspect_media(source)

    assert inspection.info.duration == 12.25
    assert inspection.info.audio_streams == 1
    assert inspection.info.video_streams == 1
    assert inspection.ffprobe == payload


def test_media_without_audio_is_rejected(monkeypatch, tmp_path):
    source = tmp_path / "silent.mp4"
    source.touch()
    payload = {"format": {"duration": "1"}, "streams": [{"codec_type": "video"}]}
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, json.dumps(payload), ""),
    )

    with pytest.raises(IHMError, match="no audio stream"):
        inspect_media(source)
