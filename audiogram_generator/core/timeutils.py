"""Pure time utility helpers used across the CLI and services."""
from __future__ import annotations


def parse_srt_time(time_str: str) -> float:
    """Convert an SRT timestamp to seconds.

    Accepts values like ``"00:00:10,500"`` and returns ``10.5``.
    """
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def format_seconds(seconds: float) -> str:
    """Format a duration in seconds as ``HH:MM:SS.mmm``.

    Keeps the sign for negative values, rounds milliseconds to 3 digits.
    """
    import math

    sign = '-' if seconds < 0 else ''
    s = abs(seconds)
    hours = int(s // 3600)
    minutes = int((s % 3600) // 60)
    secs = int(s % 60)
    millis = int(round((s - math.floor(s)) * 1000))
    return f"{sign}{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
