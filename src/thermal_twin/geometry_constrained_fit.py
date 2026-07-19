"""One-degree-of-freedom parameter mapping for a future accepted M7 fit."""

from __future__ import annotations

import math

from .geometry_constrained import GeometryConstrainedCandidate, SurfaceConstrainedPath, derive_surface_paths


def paths_from_shared_log_surface_resistance(
    candidate: GeometryConstrainedCandidate, log_surface_resistance_m2k_per_w: float
) -> tuple[SurfaceConstrainedPath, ...]:
    """Map exactly one free log r'' into N known-area branch resistances.

    This is an optimizer parameterization, not a user-entered documented
    constant.  It becomes executable only after M6 human geometry acceptance.
    """

    if not math.isfinite(log_surface_resistance_m2k_per_w):
        raise ValueError("log_surface_resistance_m2k_per_w must be finite.")
    return derive_surface_paths(
        candidate.surface_areas_m2,
        surface_resistance_m2k_per_w=math.exp(log_surface_resistance_m2k_per_w),
    )
