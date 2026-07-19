"""M6 plan inventory and geometry workflow with mandatory human acceptance.

Raw PDF vector coordinates are not silently treated as metres.  A geometry is
usable only after a reviewer has supplied/confirmed scale, north, boundary and
the remaining dimensional information required by a requested metric.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re
from typing import Iterable

import fitz
import numpy as np


PLAN_FILENAMES = (
    "Edificio PLEIADES (planta baja).pdf",
    "Edificio PLEIADES (planta 1ª).pdf",
    "Edificio PLEIADES (planta 2ª).pdf",
    "Edificio PLEIADES (planta 3ª).pdf",
    "Edificio PLEIADES (planta 4ª).pdf",
    "Edificio PLEIADES (planta 5ª).pdf",
)


@dataclass(frozen=True)
class PlanInventory:
    filename: str
    level: str
    page_count: int
    width_points: float
    height_points: float
    rotation_degrees: int
    text_characters: int
    vector_drawing_count: int
    detected_scale: str | None
    preview_path: str


@dataclass(frozen=True)
class GeometryReview:
    """Human-confirmed inputs needed before geometric metrics are usable."""

    plan_filename: str
    accepted_by_human: bool
    reviewer: str | None
    reviewed_at: str | None
    scale_metres_per_pdf_point: float | None
    north_clockwise_degrees_from_page_up: float | None
    boundary_points_pdf: tuple[tuple[float, float], ...] | None
    floor_height_m: float | None
    glazing_segments_pdf: tuple[tuple[tuple[float, float], tuple[float, float]], ...] | None
    notes: str | None = None


class GeometryValidationError(ValueError):
    """Raised instead of inventing a geometry metric from incomplete plans."""


def _level_from_filename(filename: str) -> str:
    if "baja" in filename:
        return "baja"
    match = re.search(r"planta\s+(\d+)ª", filename)
    return match.group(1) if match else "unknown"


def _detected_scale(text: str) -> str | None:
    match = re.search(r"1\s*[:/]\s*(\d+)", text)
    return f"1:{match.group(1)}" if match else None


def inventory_plans(project_root: Path | str, preview_directory: Path | str) -> list[PlanInventory]:
    """Inspect the six supplied vector PDFs and render human-review previews."""

    root = Path(project_root).resolve()
    previews = Path(preview_directory).resolve()
    previews.mkdir(parents=True, exist_ok=True)
    inventory: list[PlanInventory] = []
    for filename in PLAN_FILENAMES:
        path = root / filename
        if not path.is_file():
            raise FileNotFoundError(f"Missing supplied plan: {path}")
        document = fitz.open(path)
        if document.page_count != 1:
            raise GeometryValidationError(f"Expected exactly one page in {filename}, got {document.page_count}.")
        page = document[0]
        text = page.get_text("text")
        preview = previews / (path.stem.replace("ª", "a") + ".png")
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        pixmap.save(preview)
        inventory.append(
            PlanInventory(
                filename=filename,
                level=_level_from_filename(filename),
                page_count=document.page_count,
                width_points=float(page.rect.width),
                height_points=float(page.rect.height),
                rotation_degrees=int(page.rotation),
                text_characters=len(text.strip()),
                vector_drawing_count=len(page.get_drawings()),
                detected_scale=_detected_scale(text),
                preview_path=str(preview),
            )
        )
        document.close()
    return inventory


def _closed_non_self_intersecting(points: tuple[tuple[float, float], ...]) -> bool:
    """Small robust check for an ordinary closed polygon supplied by a reviewer."""

    if len(points) < 3:
        return False
    array = np.asarray(points, dtype=float)
    if not np.isfinite(array).all() or len(np.unique(array, axis=0)) != len(array):
        return False
    # A zero signed area is enough to reject degenerate boundary; detailed
    # self-intersection checking is handled by edge-pair orientation below.
    area_twice = np.dot(array[:, 0], np.roll(array[:, 1], -1)) - np.dot(array[:, 1], np.roll(array[:, 0], -1))
    if abs(area_twice) < 1e-10:
        return False

    def orientation(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        return float(np.cross(b - a, c - a))

    count = len(array)
    for first in range(count):
        a, b = array[first], array[(first + 1) % count]
        for second in range(first + 1, count):
            if first == second or (first + 1) % count == second or first == (second + 1) % count:
                continue
            c, d = array[second], array[(second + 1) % count]
            ab_c, ab_d = orientation(a, b, c), orientation(a, b, d)
            cd_a, cd_b = orientation(c, d, a), orientation(c, d, b)
            if ab_c * ab_d < 0.0 and cd_a * cd_b < 0.0:
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


def _orientation_bucket(azimuth_degrees: float) -> str:
    directions = ("N", "E", "S", "W")
    return directions[int(((azimuth_degrees + 45.0) % 360.0) // 90.0)]


def facade_surface_by_orientation_m2(review: GeometryReview) -> dict[str, float]:
    """Compute external boundary surface by cardinal orientation after review."""

    _require_review(review, need_height=True)
    points = np.asarray(review.boundary_points_pdf, dtype=float)
    result = {direction: 0.0 for direction in ("N", "E", "S", "W")}
    for start, end in zip(points, np.roll(points, -1, axis=0)):
        dx, dy_page_down = end - start
        # page y is down; convert to conventional y-up before deriving outward
        # segment normal.  Polygon direction does not affect surface totals.
        dx_world = dx
        dy_world = -dy_page_down
        length_m = float(math.hypot(dx_world, dy_world) * review.scale_metres_per_pdf_point)
        segment_azimuth_from_page_up = math.degrees(math.atan2(dx_world, dy_world)) % 360.0
        azimuth_from_north = (segment_azimuth_from_page_up + review.north_clockwise_degrees_from_page_up + 90.0) % 360.0
        result[_orientation_bucket(azimuth_from_north)] += length_m * float(review.floor_height_m)
    return result


def volume_m3(review: GeometryReview) -> float:
    _require_review(review, need_height=True)
    return footprint_area_m2(review) * float(review.floor_height_m)


def glazing_ratio(review: GeometryReview) -> float:
    """Return glazing/facade area only once geometry and glazing are accepted."""

    _require_review(review, need_height=True, need_glazing=True)
    facade_area = sum(facade_surface_by_orientation_m2(review).values())
    if facade_area <= 0.0:
        raise GeometryValidationError("Facade area must be positive.")
    glazing_length = sum(
        math.dist(start, end) for start, end in review.glazing_segments_pdf or ()
    ) * float(review.scale_metres_per_pdf_point)
    return float(glazing_length * float(review.floor_height_m) / facade_area)


def write_geometry_review_request(
    project_root: Path | str, inventory: Iterable[PlanInventory]
) -> Path:
    """Emit null-valued review records; they intentionally cannot feed M7."""

    root = Path(project_root).resolve()
    target = root / "runs" / "m6"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "geometry_review_request.json"
    payload = {
        "status": "HUMAN_VALIDATION_REQUIRED",
        "metrics_are_null_until_review": ["footprint_area_m2", "facade_surface_by_orientation_m2", "volume_m3", "glazing_ratio"],
        "plans": [
            {
                **asdict(record),
                "accepted_by_human": False,
                "required_confirmations": ["thermal boundary", "scale", "north", "height", "glazing when applicable"],
            }
            for record in inventory
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
