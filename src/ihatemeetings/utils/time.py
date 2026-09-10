from __future__ import annotations


def format_timestamp(
    seconds: float, *, always_hours: bool = True, milliseconds: bool = False
) -> str:
    if seconds < 0:
        raise ValueError("timestamps cannot be negative")

    whole_seconds = int(seconds)
    millis = round((seconds - whole_seconds) * 1000)
    if millis == 1000:
        whole_seconds += 1
        millis = 0

    hours, remainder = divmod(whole_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if always_hours:
        base = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        base = (
            f"{minutes:02d}:{secs:02d}" if hours == 0 else f"{hours:02d}:{minutes:02d}:{secs:02d}"
        )
    return f"{base}.{millis:03d}" if milliseconds else base
