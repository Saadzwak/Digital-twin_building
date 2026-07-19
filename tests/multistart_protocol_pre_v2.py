import numpy as np
import pandas as pd

from thermal_twin.multistart import (
    MultiStartConfig,
    StartOutcome,
    deterministic_start,
    revised_verdict,
    summarize_basins,
)
from thermal_twin.topologies import reference_model_bank


def test_starts_are_deterministic_log_uniform_and_begin_with_notebook_initialization() -> None:
    topology = reference_model_bank()[15]
    config = MultiStartConfig(n_starts=4, seed=17)
    initial, kind, seed = deterministic_start(topology, 15, 1, config)
    again, again_kind, again_seed = deterministic_start(topology, 15, 1, config)
    assert kind == again_kind == "notebook_initialization"
    assert seed is again_seed is None
    assert np.array_equal(initial, again)
    random_one, random_kind, random_seed = deterministic_start(topology, 15, 2, config)
    random_two, _, _ = deterministic_start(topology, 15, 2, config)
    bounds = np.asarray([(-10, 5)] * 4 + [(8, 25)] * 3 + [(-20, 2)], dtype=float)
    assert random_kind == "log_uniform_within_published_bounds"
    assert random_seed is not None
    assert np.array_equal(random_one, random_two)
    assert np.all(random_one >= bounds[:, 0]) and np.all(random_one <= bounds[:, 1])


def test_basin_summary_marks_train_objective_dispersion_as_initialization_sensitive() -> None:
    outcomes = []
    for start_id, mse in enumerate((1.0, 1.0, 1.5, 2.0), start=1):
        outcomes.append(StartOutcome(
            model="synthetic", model_index=0, start_id=start_id, start_kind="test", start_seed=start_id,
            initial_parameters_log=(0.0,), final_parameters_log=(float(start_id),), fit_success=True,
            fit_status=0, fit_message="ok", nfev=1, nit=1, train_mse=mse, train_rmse=float(np.sqrt(mse)),
            validation_rmse=10.0 - start_id, validation_bic=100.0 - start_id, test_rmse=1.0, error=None,
            selected_by_train_mse=start_id == 1,
        ))
    summary = summarize_basins("synthetic", 0, outcomes, 4)
    assert summary.selected_start_id == 1
    assert summary.objective_basin_count > 1
    assert summary.identification_confidence == "sensitive_to_initialization"


def test_revised_b_verdict_uses_oracle_uniformity_and_dispersion_not_validation_selection() -> None:
    selected = []
    summaries = []
    for index, topology in enumerate(reference_model_bank()):
        selected.append({
            "model": topology.name, "model_index": index, "selected_start_id": 1,
            "train_mse": 1.0, "validation_rmse": 5.0,
            "validation_bic": 1000.0 + index, "test_rmse": 1.0, "fit_success": True,
            "duplicate_of": topology.duplicate_of,
        })
        summaries.append({"model": topology.name, "identification_confidence": "sensitive_to_initialization"})
    merged = {"config": {"n_starts": 4, "seed": 17, "dt_seconds": 3600.0}, "outcomes": [{}] * 76, "selected": selected, "basin_summaries": summaries}
    oracle = {"passed": True}
    verdict = revised_verdict(merged, oracle)
    assert verdict["verdict"] == "B"
    assert verdict["validated"] is True
    assert verdict["sensitivity_banner_required"] is True
