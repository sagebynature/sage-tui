"""Small utility functions shared across sage-tui modules."""

from __future__ import annotations

from typing import Any


def format_tokens(count: int) -> str:
    """Format a token count as a human-readable string (e.g. 1234 → '1.2k')."""
    if count < 1000:
        return str(count)
    if count < 1_000_000:
        return f"{count / 1000:.1f}k"
    return f"{count / 1_000_000:.1f}M"


def fmt_args(arguments: dict[str, Any]) -> str:
    """Return a brief, single-line representation of tool arguments."""
    if not arguments:
        return ""
    parts: list[str] = []
    for k, v in list(arguments.items())[:3]:
        val_str = str(v)
        if len(val_str) > 20:
            val_str = val_str[:20] + "…"
        parts.append(f"{k}={val_str!r}")
    if len(arguments) > 3:
        parts.append("…")
    return ", ".join(parts)
