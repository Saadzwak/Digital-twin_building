from pathlib import Path

import pytest

from thermal_twin.dashboard_contract import DashboardPayload, IntervalEstimate, require_dashboard_access
from thermal_twin.validation_gate import M4ValidationError, load_m4_verdict


def test_estimate_cannot_be_displayed_without_complete_uncertainty_provenance() -> None:
    estimate = IntervalEstimate(10.0, 8.0, 12.0, "W/K", "validation", "block bootstrap", "run-x")
    assert estimate.value == 10.0
    with pytest.raises(ValueError, match="inside"):
        IntervalEstimate(13.0, 8.0, 12.0, "W/K", "validation", "bootstrap", "run-x")
    with pytest.raises(ValueError, match="unit"):
        IntervalEstimate(10.0, 8.0, 12.0, "", "validation", "bootstrap", "run-x")


def test_effective_loss_paths_cannot_claim_individual_walls() -> None:
    estimate = IntervalEstimate(10.0, 8.0, 12.0, "W/K", "validation", "wall loss estimate", "run-x")
    with pytest.raises(ValueError, match="walls"):
        DashboardPayload("run-x", "4R3C", "success", "effective state only", (estimate,), (), (), (), ())


def test_actual_dashboard_gate_blocks_or_accepts_the_current_m4_verdict() -> None:
    root = Path(__file__).resolve().parents[1]
    verdict = load_m4_verdict(root)
    if verdict.get("validated") is not True:
        with pytest.raises(M4ValidationError, match="not validated"):
            require_dashboard_access(root)
        return
    accepted = require_dashboard_access(root)
    assert accepted["validation_route"] in {"A", "B"}
    assert accepted["protocol"] == "uniform_multistart_notebook_cell_55"
    if accepted["validation_route"] == "B":
        assert accepted["sensitivity_banner_required"] is True
