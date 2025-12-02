"""Rendering layer facade(s).

Thin wrappers around the legacy video generator to provide a stable, simple
API for the CLI without exposing low-level details. This keeps dependency
direction one‑way (CLI -> rendering) and simplifies future refactors.
"""

__all__ = [
    "facade",
]
