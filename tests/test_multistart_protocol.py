from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

import thermal_twin.multistart_impl as implementation
from thermal_twin.multistart import (
    MultiStartConfig,
    StartOutcome,
    deterministic_start,
    revised_verdict,
    run_model_multistart,
    summarize_basins,
)
from thermal_twin.topologies import reference_model_bank


def test_starts_are_deterministic_log_uniform_notebook_first_and_profile_matched() -> None:
    bank = reference_model_bank()
    config = MultiStartConfig(n_starts=32, seed=7096790)
    topology = bank[15]
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
    # The intentionally duplicated 1R1C labels remain separate runs but use
    # the same bank because they have the same parameter profile.
    duplicate_a, _, _ = deterministic_start(bank[0], 0, 9, config)
    duplicate_b, _, _ = deterministic_start(bank[10], 10, 9, config)
    assert np.array_equal(duplicate_a, duplicate_b)


def test_train_mse_selects_even_a_nonconverged_fit_when_validation_prefers_another(
    monkeypatch,
) -> None:
    topology = reference_model_bank()[0]
    config = MultiStartConfig(n_starts=3, seed=1)
    starts = tuple(
        (np.asarray([float(start_id)]), "test", start_id)
        for start_id in range(1, 4)
    )

    def fake_fit(_topology, _train, initial, _dt):
        start_id = int(initial[0])
        mse = {1: 3.0, 2: 1.0, 3: 2.0}[start_id]
        fitted = SimpleNamespace(
            success=start_id != 2,
            status=1 if start_id == 2 else 0,
            message="nonconverged" if start_id == 2 else "ok",
            nfev=1,
            nit=1,
            parameters_log=np.asarray([float(start_id)]),
        )
        metrics = SimpleNamespace(rss=mse * 10.0, n_observations=10, rmse=np.sqrt(mse))
        return fitted, SimpleNamespace(metrics=metrics)

    def fake_evaluate(fitted, _frame, _dt):
        start_id = int(fitted.parameters_log[0])
        # Start 3 is best on validation; that must not affect selection.
        metrics = SimpleNamespace(rmse=float(10 - start_id), bic=float(100 - 10 * start_id))
        return SimpleNamespace(metrics=metrics)

    monkeypatch.setattr(implementation, "build_start_bank", lambda *_: starts)
    monkeypatch.setattr(implementation, "fit_from_initial_parameters", fake_fit)
    monkeypatch.setattr(implementation, "evaluate_topology", fake_evaluate)
    frames = pd.DataFrame()
    outcomes, selected, _summary = run_model_multistart(topology, 0, frames, frames, frames, config)
    assert selected is not None
    assert selected.selected_start_id == 2
    assert selected.fit_success is False
    assert outcomes[1].selected_by_train_mse is True
    assert outcomes[2].validation_bic < outcomes[1].validation_bic


def test_basin_summary_marks_train_objective_dispersion_as_initialization_sensitive() -> None:
    outcomes = []
    for start_id, mse in enumerate((1.0, 1.0, 1.5, 2.0), start=1):
        outcomes.append(
            StartOutcome(
                model="synthetic", model_index=0, start_id=start_id, start_kind="test", start_seed=start_id,
                initial_parameters_log=(0.0,), final_parameters_log=(float(start_id),), fit_success=True,
                fit_status=0, fit_message="ok", nfev=1, nit=1, train_mse=mse, train_rmse=float(np.sqrt(mse)),
                validation_rmse=10.0 - start_id, validation_bic=100.0 - start_id, test_rmse=1.0, error=None,
                selected_by_train_mse=start_id == 1,
            )
        )
    summary = summarize_basins("synthetic", 0, outcomes, 4)
    assert summary.selected_start_id == 1
    assert summary.objective_basin_count > 1
    assert summary.identification_confidence == "sensitive_to_initialization"
    assert summary.near_best_train_fraction == 0.5


def test_revised_b_verdict_requires_oracle_uniformity_and_dispersion() -> None:
    selected = []
    summaries = []
    outcomes = []
    for index, topology in enumerate(reference_model_bank()):
        selected.append(
            {
                "model": topology.name, "model_index": index, "selected_start_id": 1,
                "train_mse": 1.0, "validation_rmse": 5.0,
                "validation_bic": 1000.0 + index, "test_rmse": 1.0, "fit_success": True,
                "duplicate_of": topology.duplicate_of,
            }
        )
        summaries.append(
            {"model": topology.name, "n_starts": 4, "identification_confidence": "sensitive_to_initialization"}
        )
        outcomes.extend({"model_index": index, "start_id": start_id} for start_id in range(1, 5))
    merged = {
        "config": {"n_starts": 4, "seed": 17, "dt_seconds": 3600.0, "rng": "numpy.random.PCG64"},
        "outcomes": outcomes,
        "selected": selected,
        "basin_summaries": summaries,
    }
    verdict = revised_verdict(merged, {"passed": True})
    assert verdict["verdict"] == "B"
    assert verdict["validated"] is True
    assert verdict["sensitivity_banner_required"] is True
    assert verdict["criterion_b"]["uniform_protocol"] is True


def test_route_a_requires_predeclared_strong_bic_gap() -> None:
    bank = reference_model_bank()
    std4_index = next(index for index, item in enumerate(bank) if item.name.startswith("STD_4R3C"))
    selected = []
    outcomes = []
    summaries = []
    for index, topology in enumerate(bank):
        bic = 1000.0 + index
        if index == std4_index:
            bic = 900.0
        selected.append({"model": topology.name, "model_index": index, "selected_start_id": 1, "train_mse": 1.0, "validation_rmse": 5.0, "validation_bic": bic, "test_rmse": 1.0, "fit_success": True, "duplicate_of": topology.duplicate_of})
        summaries.append({"model": topology.name, "n_starts": 2, "identification_confidence": "stable_over_sampled_starts"})
        outcomes.extend({"model_index": index, "start_id": start_id} for start_id in (1, 2))
    verdict = revised_verdict({"config": {"n_starts": 2}, "outcomes": outcomes, "selected": selected, "basin_summaries": summaries}, {"passed": True})
    assert verdict["verdict"] == "A"
    assert verdict["criterion_a"]["bic_gap_to_next"] >= 10.0
