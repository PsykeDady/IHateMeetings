from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ihatemeetings.errors import IHMError
from ihatemeetings.models import MediaInfo

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".mkv", ".mp4", ".webm"}


@dataclass(frozen=True)
class MediaInspection:
    info: MediaInfo
    ffprobe: dict[str, Any]


def inspect_media(source: Path) -> MediaInspection:
    if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise IHMError(
            f"Unsupported media type: {source.suffix or '(none)'}. Supported: {supported}"
        )
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(source),
    ]
    result = _run(command, "FFprobe")
    try:
        payload = json.loads(result.stdout)
        streams = payload.get("streams", [])
        format_data = payload.get("format", {})
        duration = _float_or_none(format_data.get("duration"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise IHMError("FFprobe returned invalid media metadata.") from exc
    audio_streams = sum(stream.get("codec_type") == "audio" for stream in streams)
    if not audio_streams:
        raise IHMError("The input contains no audio stream.")
    if duration is None:
        durations = [_float_or_none(stream.get("duration")) for stream in streams]
        duration = max((value for value in durations if value is not None), default=None)
    if duration is None or duration < 0:
        raise IHMError("FFprobe could not determine a valid media duration.")
    info = MediaInfo(
        source=source.resolve(),
        duration=duration,
        format_name=str(format_data.get("format_name", "unknown")),
        size_bytes=_int_or_none(format_data.get("size")),
        start_time=_float_or_none(format_data.get("start_time")),
        audio_streams=audio_streams,
        video_streams=sum(stream.get("codec_type") == "video" for stream in streams),
    )
    return MediaInspection(info=info, ffprobe=payload)


def extract_audio(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    command = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    _run(command, "FFmpeg")


def _run(command: list[str], tool_name: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise IHMError(
            f"{tool_name} is not installed.",
            "Install the FFmpeg package for your distribution, then run 'ihm doctor'.",
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or "unknown error"
        raise IHMError(f"{tool_name} failed: {detail}") from exc


def _float_or_none(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
