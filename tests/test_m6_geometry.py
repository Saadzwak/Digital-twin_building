from pathlib import Path

import pytest

from thermal_twin.geometry import (
    GeometryReview,
    GeometryValidationError,
    facade_surface_by_orientation_m2,
    footprint_area_m2,
    glazing_ratio,
    inventory_plans,
    volume_m3,
)


def _accepted_square() -> GeometryReview:
    return GeometryReview(
        plan_filename="synthetic.pdf",
        accepted_by_human=True,
        reviewer="test reviewer",
        reviewed_at="2026-07-18T00:00:00Z",
        scale_metres_per_pdf_point=0.1,
        north_clockwise_degrees_from_page_up=0.0,
        boundary_points_pdf=((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
        floor_height_m=3.0,
        glazing_segments_pdf=(((0.0, 0.0), (50.0, 0.0)),),
    )


def test_geometry_metrics_follow_an_accepted_calibrated_square() -> None:
    review = _accepted_square()
    assert footprint_area_m2(review) == pytest.approx(100.0)
    assert volume_m3(review) == pytest.approx(300.0)
    assert sum(facade_surface_by_orientation_m2(review).values()) == pytest.approx(120.0)
    assert glazing_ratio(review) == pytest.approx(0.125)


def test_geometry_refuses_unreviewed_or_incomplete_inputs() -> None:
    review = _accepted_square()
    unreviewed = GeometryReview(**{**review.__dict__, "accepted_by_human": False})
    with pytest.raises(GeometryValidationError, match="human reviewer"):
        footprint_area_m2(unreviewed)
    missing_height = GeometryReview(**{**review.__dict__, "floor_height_m": None})
    with pytest.raises(GeometryValidationError, match="floor height"):
        volume_m3(missing_height)


def test_actual_plan_inventory_has_six_single_page_records_in_workspace_tmp() -> None:
    root = Path(__file__).resolve().parents[1]
    inventory = inventory_plans(root, root / "tmp" / "m6_test_previews")
    assert len(inventory) == 6
    assert all(record.page_count == 1 for record in inventory)
    assert all(Path(record.preview_path).is_file() for record in inventory)
