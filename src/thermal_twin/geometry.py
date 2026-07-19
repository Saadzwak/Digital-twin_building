"""Human-gated geometry helpers with orientation-invariant facade totals."""

from __future__ import annotations

import math

import numpy as np

from . import geometry_impl as _implementation
from .geometry_impl import (  # noqa: F401
    PLAN_FILENAMES,
    GeometryReview,
    GeometryValidationError,
    PlanInventory,
    footprint_area_m2,
    glazing_ratio,
    inventory_plans,
    volume_m3,
    write_geometry_review_request,
)


def facade_surface_by_orientation_m2(review: GeometryReview) -> dict[str, float]:
    """Return exterior facade area by orientation, invariant to vertex order.

    PDF coordinates have y increasing downwards.  We convert to y-up world
    coordinates, infer whether the polygon is clockwise or counter-clockwise,
    then choose the outward (rather than an arbitrary) normal for each edge.
    """

    _implementation._require_review(review, need_height=True)
    page_points = np.asarray(review.boundary_points_pdf, dtype=float)
    world_points = page_points.copy()
    world_points[:, 1] *= -1.0
    signed_area = 0.5 * (
        np.dot(world_points[:, 0], np.roll(world_points[:, 1], -1))
        - np.dot(world_points[:, 1], np.roll(world_points[:, 0], -1))
    )
    if signed_area == 0.0:
        raise GeometryValidationError("Thermal boundary has zero signed area.")
    # For CCW vertices, the exterior lies to the right (+90° clockwise from
    # north-based tangent azimuth).  For CW vertices it lies to the left.
    outward_turn = 90.0 if signed_area > 0.0 else -90.0
    result = {direction: 0.0 for direction in ("N", "E", "S", "W")}
    for start, end in zip(world_points, np.roll(world_points, -1, axis=0)):
        dx, dy = end - start
        length_m = float(math.hypot(dx, dy) * review.scale_metres_per_pdf_point)
        tangent_from_page_up = math.degrees(math.atan2(dx, dy)) % 360.0
        outward_from_north = (
            tangent_from_page_up
            + float(review.north_clockwise_degrees_from_page_up)
            + outward_turn
        ) % 360.0
        result[_implementation._orientation_bucket(outward_from_north)] += (
            length_m * float(review.floor_height_m)
        )
    return result


__all__ = [
    "PLAN_FILENAMES", "GeometryReview", "GeometryValidationError", "PlanInventory", "inventory_plans",
    "write_geometry_review_request", "footprint_area_m2", "facade_surface_by_orientation_m2", "volume_m3", "glazing_ratio",
]
