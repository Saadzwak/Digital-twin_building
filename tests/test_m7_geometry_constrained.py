from pathlib import Path

import pytest

from thermal_twin.geometry import GeometryReview, GeometryValidationError
from thermal_twin.geometry_constrained import (
    GeometryConstrainedCandidate,
    aggregate_boundary_conductance_w_per_k,
    candidate_from_accepted_geometry,
    derive_surface_paths,
    require_ready_for_real_geometry_fit,
)
from thermal_twin.validation_gate import M4ValidationError, load_m4_verdict


def _review(accepted: bool = True) -> GeometryReview:
    return GeometryReview(
        plan_filename="synthetic.pdf",
        accepted_by_human=accepted,
        reviewer="reviewer" if accepted else None,
        reviewed_at="2026-07-18T00:00:00Z" if accepted else None,
        scale_metres_per_pdf_point=0.1,
        north_clockwise_degrees_from_page_up=0.0,
        boundary_points_pdf=((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
        floor_height_m=3.0,
        glazing_segments_pdf=None,
    )


def test_n_surface_branches_have_one_free_surface_parameter_and_aggregate_exactly() -> None:
    candidate = GeometryConstrainedCandidate("synthetic", {"N": 10.0, "E": 20.0, "S": 30.0})
    paths = derive_surface_paths(candidate.surface_areas_m2, surface_resistance_m2k_per_w=5.0)
    assert candidate.free_surface_parameters == 1
    assert [path.resistance_k_per_w for path in paths] == [0.5, 0.25, 1.0 / 6.0]
    assert aggregate_boundary_conductance_w_per_k(paths) == pytest.approx(12.0)
    assert aggregate_boundary_conductance_w_per_k(paths) == pytest.approx(sum(candidate.surface_areas_m2.values()) / 5.0)


def test_geometry_candidate_requires_human_accepted_inputs() -> None:
    with pytest.raises(GeometryValidationError, match="human reviewer"):
        candidate_from_accepted_geometry(_review(accepted=False))


def test_real_geometry_fit_is_gated_or_reduces_to_one_surface_parameter() -> None:
    root = Path(__file__).resolve().parents[1]
    verdict = load_m4_verdict(root)
    if verdict.get("validated") is not True:
        with pytest.raises(M4ValidationError, match="not validated"):
            require_ready_for_real_geometry_fit(root, _review())
        return
    candidate = require_ready_for_real_geometry_fit(root, _review())
    assert candidate.free_surface_parameters == 1
    assert candidate.surface_areas_m2
