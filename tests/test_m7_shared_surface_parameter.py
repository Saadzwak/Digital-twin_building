import math

import pytest

from thermal_twin.geometry_constrained import GeometryConstrainedCandidate
from thermal_twin.geometry_constrained_fit import paths_from_shared_log_surface_resistance


def test_one_log_surface_parameter_controls_all_known_surface_branches() -> None:
    candidate = GeometryConstrainedCandidate("synthetic", {"N": 10.0, "E": 20.0, "S": 40.0})
    paths = paths_from_shared_log_surface_resistance(candidate, math.log(8.0))
    assert candidate.free_surface_parameters == 1
    assert [path.resistance_k_per_w for path in paths] == pytest.approx([0.8, 0.4, 0.2])
