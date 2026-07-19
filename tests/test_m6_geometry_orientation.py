from __future__ import annotations

import pytest

from thermal_twin.geometry import GeometryReview, facade_surface_by_orientation_m2


def _review(points: tuple[tuple[float, float], ...]) -> GeometryReview:
    return GeometryReview(
        plan_filename="synthetic.pdf",
        accepted_by_human=True,
        reviewer="test reviewer",
        reviewed_at="2026-07-18T00:00:00Z",
        scale_metres_per_pdf_point=0.1,
        north_clockwise_degrees_from_page_up=0.0,
        boundary_points_pdf=points,
        floor_height_m=3.0,
        glazing_segments_pdf=None,
    )


def test_facade_orientation_is_invariant_when_boundary_vertex_order_is_reversed() -> None:
    clockwise = ((0.0, 0.0), (100.0, 0.0), (100.0, 40.0), (0.0, 40.0))
    counter_clockwise = tuple(reversed(clockwise))
    forward = facade_surface_by_orientation_m2(_review(clockwise))
    reverse = facade_surface_by_orientation_m2(_review(counter_clockwise))
    assert forward == pytest.approx(reverse)
    assert sum(forward.values()) == pytest.approx(84.0)
