"""Public M4 multi-start API.

The implementation is kept in ``multistart_impl`` so the local Windows
sandbox can apply narrowly scoped corrective patches without changing the
frozen historical implementation backup.  Public names remain stable.
"""

from __future__ import annotations

from collections.abc import Sequence

from . import multistart_impl as _implementation


def _quantile(values: Sequence[float], probability: float) -> float | None:
    """Return a finite sample quantile, accepting both lists and ndarrays."""

    if len(values) == 0:
        return None
    return float(_implementation.np.quantile(_implementation.np.asarray(values, dtype=float), probability))


# ``summarize_basins`` resolves this helper in its defining module.  Patching
# it once at import fixes ndarray truth-value ambiguity without changing any
# frozen identification behavior.
_implementation._quantile = _quantile

from .multistart_impl import *  # noqa: F401,F403,E402
