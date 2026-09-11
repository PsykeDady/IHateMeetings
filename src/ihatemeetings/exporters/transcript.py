from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ihatemeetings.models import Transcript
from ihatemeetings.review.effective import EffectiveSegment, canonical_payload, effective_segments
from ihatemeetings.utils.time import format_timestamp


def export_all(transcript: Transcript, output_dir: Path) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    rendered = render_all(transcript)
    outputs = tuple(output_dir / name for name in rendered)
    for path in outputs:
        _write_private(path, rendered[path.name])
    return outputs


def render_all(transcript: Transcript) -> dict[str, str]:
    return {
        "transcript.json": json.dumps(canonical_payload(transcript), indent=2) + "\n",
        "transcript.md": render_markdown(transcript),
        "transcript.txt": render_text(transcript),
        "transcript.srt": render_srt(transcript),
        "transcript.vtt": render_vtt(transcript),
    }


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
    for segment in effective_segments(transcript):
        lines.extend(
            [
                f"### [{format_timestamp(segment.start)}] {segment.attribution.label}",
                "",
                segment.text,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_text(transcript: Transcript) -> str:
    return "\n\n".join(
        f"[{format_timestamp(segment.start)}] {segment.attribution.label}\n{segment.text}"
        for segment in effective_segments(transcript)
    ) + ("\n" if effective_segments(transcript) else "")


def render_srt(transcript: Transcript) -> str:
    blocks = []
    for index, segment in enumerate(effective_segments(transcript), 1):
        start = _subtitle_timestamp(segment.start, comma=True)
        end = _subtitle_timestamp(segment.end, comma=True)
        blocks.append(f"{index}\n{start} --> {end}\n{_subtitle_text(segment)}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def render_vtt(transcript: Transcript) -> str:
    blocks = ["WEBVTT"]
    for segment in effective_segments(transcript):
        start = _subtitle_timestamp(segment.start, comma=False)
        end = _subtitle_timestamp(segment.end, comma=False)
        blocks.append(f"{start} --> {end}\n{_subtitle_text(segment)}")
    return "\n\n".join(blocks) + "\n"


def _subtitle_timestamp(seconds: float, *, comma: bool) -> str:
    timestamp = format_timestamp(seconds, milliseconds=True)
    return timestamp.replace(".", ",") if comma else timestamp


def _subtitle_text(segment: EffectiveSegment) -> str:
    if segment.attribution.layer == "phase3_unknown":
        return segment.text
    return f"[{segment.attribution.label}] {segment.text}"


def _write_private(path: Path, content: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
