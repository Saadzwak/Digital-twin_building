"""M7 geometry-constrained boundary paths without false per-wall identifiability."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

from .geometry import GeometryReview, facade_surface_by_orientation_m2
from .validation_gate import require_validated_m4


@dataclass(frozen=True)
class SurfaceConstrainedPath:
    """Derived branch data; no branch resistance is independently fitted."""

    orientation: str
    area_m2: float
    resistance_k_per_w: float


@dataclass(frozen=True)
class GeometryConstrainedCandidate:
    """A candidate with exactly one surface-resistance parameter r''."""

    name: str
    surface_areas_m2: Mapping[str, float]
    free_surface_parameters: int = 1
    identifiability_note: str = (
        "With one shared Tout forcing, orientation branches aggregate; individual façade losses are not identifiable."
    )

    def __post_init__(self) -> None:
        if self.free_surface_parameters != 1:
            raise ValueError("Geometry must reduce to exactly one shared surface-resistance parameter.")
        if not self.surface_areas_m2 or any(not np.isfinite(area) or area <= 0.0 for area in self.surface_areas_m2.values()):
            raise ValueError("Every geometry-constrained surface must have a finite positive known area.")


def derive_surface_paths(
    surface_areas_m2: Mapping[str, float], surface_resistance_m2k_per_w: float
) -> tuple[SurfaceConstrainedPath, ...]:
    """Apply R_i = r'' / A_i from one common resistance per unit area."""

    if not np.isfinite(surface_resistance_m2k_per_w) or surface_resistance_m2k_per_w <= 0.0:
        raise ValueError("surface_resistance_m2k_per_w must be finite and positive.")
    candidate = GeometryConstrainedCandidate("validation", surface_areas_m2)
    return tuple(
        SurfaceConstrainedPath(
            orientation=orientation,
            area_m2=float(area),
            resistance_k_per_w=float(surface_resistance_m2k_per_w / area),
        )
        for orientation, area in candidate.surface_areas_m2.items()
    )


def aggregate_boundary_conductance_w_per_k(paths: tuple[SurfaceConstrainedPath, ...]) -> float:
    """Sum conductances; the only identifiable result when all branches share Tout."""

    if not paths:
        raise ValueError("At least one constrained path is required.")
    return float(sum(1.0 / path.resistance_k_per_w for path in paths))


def candidate_from_accepted_geometry(review: GeometryReview) -> GeometryConstrainedCandidate:
    """Create a candidate only from a human-accepted thermal-boundary review."""

    areas = facade_surface_by_orientation_m2(review)
    known = {orientation: area for orientation, area in areas.items() if area > 0.0}
    return GeometryConstrainedCandidate(
        name=f"GEOMETRY_CONSTRAINED_{review.plan_filename}",
        surface_areas_m2=known,
    )


def require_ready_for_real_geometry_fit(project_root: Path | str, review: GeometryReview) -> GeometryConstrainedCandidate:
    """Require both M4 validation and M6 human acceptance before M7 real fitting."""

    require_validated_m4(project_root)
    return candidate_from_accepted_geometry(review)
