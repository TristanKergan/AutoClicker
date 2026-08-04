"""Interval unit conversion helpers.

The UI lets the user express the click interval in milliseconds, seconds,
minutes, or hours. Internally the engine always works in seconds.
"""
from __future__ import annotations

# Multipliers that convert one *value* in the given unit into seconds.
UNIT_TO_SECONDS: dict[str, float] = {
    "ms": 1e-3,
    "sec": 1.0,
    "min": 60.0,
    "hour": 3600.0,
}

UNIT_LABELS: dict[str, str] = {
    "ms": "milliseconds",
    "sec": "seconds",
    "min": "minutes",
    "hour": "hours",
}

# Sensible minimum value per unit (keeps the UI from entering absurd values).
UNIT_MIN: dict[str, float] = {
    "ms": 1.0,
    "sec": 0.01,
    "min": 0.01,
    "hour": 0.01,
}

UNIT_MAX: dict[str, float] = {
    "ms": 100_000.0,
    "sec": 100_000.0,
    "min": 10_000.0,
    "hour": 1_000.0,
}


def to_seconds(value: float, unit: str) -> float:
    return float(value) * UNIT_TO_SECONDS.get(unit, 1.0)


def to_milliseconds(value: float, unit: str) -> float:
    return to_seconds(value, unit) * 1000.0


def format_milliseconds(ms: float) -> str:
    """Human-readable interval, e.g. ``50 ms``, ``1.50 sec``, ``5.0 min``."""
    if ms < 1000:
        return f"{ms:.0f} ms"
    if ms < 60_000:
        return f"{ms / 1000:.2f} sec"
    if ms < 3_600_000:
        return f"{ms / 60_000:.1f} min"
    return f"{ms / 3_600_000:.1f} hour"
