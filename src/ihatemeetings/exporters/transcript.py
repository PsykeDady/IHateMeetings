from __future__ import annotations

import json
from pathlib import Path

from ihatemeetings.models import Transcript
from ihatemeetings.utils.time import format_timestamp


def export_all(transcript: Transcript, output_dir: Path) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    outputs = (
        output_dir / "transcript.json",
        output_dir / "transcript.md",
        output_dir / "transcript.txt",
        output_dir / "transcript.srt",
        output_dir / "transcript.vtt",
    )
    _write_private(outputs[0], json.dumps(transcript.to_dict(), indent=2) + "\n")
    _write_private(outputs[1], render_markdown(transcript))
    _write_private(outputs[2], render_text(transcript))
    _write_private(outputs[3], render_srt(transcript))
    _write_private(outputs[4], render_vtt(transcript))
    return outputs


def render_markdown(transcript: Transcript) -> str:
    language = transcript.language or "unknown"
    lines = [
        "# Meeting transcript",
        "",
        f"**Source:** {transcript.source}",
        f"**Language:** {language}",
        f"**Duration:** {format_timestamp(transcript.duration)}",
        "",
        "## Transcript",
        "",
    ]
    for segment in transcript.segments:
        lines.extend([f"### [{format_timestamp(segment.start)}] UNKNOWN [?]", "", segment.text, ""])
    return "\n".join(lines).rstrip() + "\n"


def render_text(transcript: Transcript) -> str:
    return "\n\n".join(
        f"[{format_timestamp(segment.start)}] UNKNOWN [?]\n{segment.text}"
        for segment in transcript.segments
    ) + ("\n" if transcript.segments else "")


def render_srt(transcript: Transcript) -> str:
    blocks = []
    for index, segment in enumerate(transcript.segments, 1):
        start = _subtitle_timestamp(segment.start, comma=True)
        end = _subtitle_timestamp(segment.end, comma=True)
        blocks.append(f"{index}\n{start} --> {end}\n{segment.text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def render_vtt(transcript: Transcript) -> str:
    blocks = ["WEBVTT"]
    for segment in transcript.segments:
        start = _subtitle_timestamp(segment.start, comma=False)
        end = _subtitle_timestamp(segment.end, comma=False)
        blocks.append(f"{start} --> {end}\n{segment.text}")
    return "\n\n".join(blocks) + "\n"


def _subtitle_timestamp(seconds: float, *, comma: bool) -> str:
    timestamp = format_timestamp(seconds, milliseconds=True)
    return timestamp.replace(".", ",") if comma else timestamp


def _write_private(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)
