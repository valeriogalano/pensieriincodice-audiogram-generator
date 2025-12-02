"""
Core utilities and domain helpers for the Audiogram Generator.

This package hosts pure, side‑effect‑free logic extracted from the
monolithic CLI module to improve testability and modularity.
"""

__all__ = [
    "parse_srt_time",
    "format_seconds",
    "parse_episode_selection",
    "parse_soundbite_selection",
]

from .timeutils import parse_srt_time, format_seconds
from .selections import parse_episode_selection, parse_soundbite_selection
