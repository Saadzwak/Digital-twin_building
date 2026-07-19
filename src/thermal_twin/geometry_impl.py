"""Human-gated plan geometry, with NumPy-2-safe polygon validation.

The initial implementation remains in ``geometry_legacy`` for audit history.
This public module replaces only geometric metric helpers to remove a deprecated
two-dimensional ``np.cross`` use uncovered by M6 tests.
"""

from __future__ import annotations

import math

import numpy as np

from .geometry_legacy import (
    PLAN_FILENAMES,
    GeometryReview,
    GeometryValidationError,
    PlanInventory,
    _orientation_bucket,
    inventory_plans,
    write_geometry_review_request,
)


def _cross_z(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _closed_non_self_intersecting(points: tuple[tuple[float, float], ...]) -> bool:
    if len(points) < 3:
        return False
    array = np.asarray(points, dtype=float)
    if not np.isfinite(array).all() or len(np.unique(array, axis=0)) != len(array):
        return False
    area_twice = np.dot(array[:, 0], np.roll(array[:, 1], -1)) - np.dot(array[:, 1], np.roll(array[:, 0], -1))
    if abs(area_twice) < 1e-10:
        return False
    count = len(array)
    for first in range(count):
        a, b = array[first], array[(first + 1) % count]
        for second in range(first + 1, count):
            if first == second or (first + 1) % count == second or first == (second + 1) % count:
                continue
            c, d = array[second], array[(second + 1) % count]
            if _cross_z(a, b, c) * _cross_z(a, b, d) < 0.0 and _cross_z(c, d, a) * _cross_z(c, d, b) < 0.0:
                return False
    return True


def _require_review(review: GeometryReview, *, need_height: bool = False, need_glazing: bool = False) -> None:
    if not review.accepted_by_human:
        raise GeometryValidationError("Geometry is not usable until a human reviewer accepts it.")
    if not review.reviewer or not review.reviewed_at:
        raise GeometryValidationError("Accepted geometry must record reviewer and review timestamp.")
    if review.scale_metres_per_pdf_point is None or review.scale_metres_per_pdf_point <= 0.0:
        raise GeometryValidationError("A positive human-confirmed scale is required.")
    if review.north_clockwise_degrees_from_page_up is None:
        raise GeometryValidationError("A human-confirmed north orientation is required.")
    if review.boundary_points_pdf is None or not _closed_non_self_intersecting(review.boundary_points_pdf):
        raise GeometryValidationError("A non-self-intersecting accepted thermal boundary is required.")
    if need_height and (review.floor_height_m is None or review.floor_height_m <= 0.0):
        raise GeometryValidationError("A positive confirmed floor height is required.")
    if need_glazing and review.glazing_segments_pdf is None:
        raise GeometryValidationError("Accepted glazing segments are required.")


def footprint_area_m2(review: GeometryReview) -> float:
    _require_review(review)
    points = np.asarray(review.boundary_points_pdf, dtype=float)
    signed_area = 0.5 * (np.dot(points[:, 0], np.roll(points[:, 1], -1)) - np.dot(points[:, 1], np.roll(points[:, 0], -1)))
    return float(abs(signed_area) * review.scale_metres_per_pdf_point**2)


def facade_surface_by_orientation_m2(review: GeometryReview) -> dict[str, float]:
    _require_review(review, need_height=True)
    points = np.asarray(review.boundary_points_pdf, dtype=float)
    result = {direction: 0.0 for direction in ("N", "E", "S", "W")}
    for start, end in zip(points, np.roll(points, -1, axis=0)):
        dx, dy_page_down = end - start
        dx_world, dy_world = dx, -dy_page_down
        length_m = float(math.hypot(dx_world, dy_world) * review.scale_metres_per_pdf_point)
        segment_azimuth_from_page_up = math.degrees(math.atan2(dx_world, dy_world)) % 360.0
        azimuth_from_north = (segment_azimuth_from_page_up + review.north_clockwise_degrees_from_page_up + 90.0) % 360.0
        result[_orientation_bucket(azimuth_from_north)] += length_m * float(review.floor_height_m)
    return result


def volume_m3(review: GeometryReview) -> float:
    _require_review(review, need_height=True)
    return footprint_area_m2(review) * float(review.floor_height_m)


def glazing_ratio(review: GeometryReview) -> float:
    _require_review(review, need_height=True, need_glazing=True)
    facade_area = sum(facade_surface_by_orientation_m2(review).values())
    if facade_area <= 0.0:
        raise GeometryValidationError("Facade area must be positive.")
    glazing_length = sum(math.dist(start, end) for start, end in review.glazing_segments_pdf or ())
    glazing_length *= float(review.scale_metres_per_pdf_point)
    return float(glazing_length * float(review.floor_height_m) / facade_area)


__all__ = [
    "PLAN_FILENAMES", "GeometryReview", "GeometryValidationError", "PlanInventory", "inventory_plans",
    "write_geometry_review_request", "footprint_area_m2", "facade_surface_by_orientation_m2", "volume_m3", "glazing_ratio",
]
