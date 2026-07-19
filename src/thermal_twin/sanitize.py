"""Recursively replace NaN/Inf with None before any value reaches the wire.

Vega/Altair raised "Infinite extent" because NaN/Inf leaked into series. The web
app renders its own SVG, but this guard stays the single choke point: every JSON
payload leaving the API passes through :func:`clean` so no non-finite number can
reach the client, whatever its origin.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def clean(value: Any) -> Any:
    """Return a JSON-safe copy with every non-finite float replaced by None."""

    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def finite_series(pairs: list[tuple[Any, Any]]) -> list[list[Any]]:
    """Keep only [x, y] points whose y is a finite number (x kept as-is)."""

    result: list[list[Any]] = []
    for x, y in pairs:
        if isinstance(y, (int, np.integer)):
            result.append([x, int(y)])
        elif isinstance(y, (float, np.floating)) and math.isfinite(float(y)):
            result.append([x, float(y)])
    return result
