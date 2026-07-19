import numpy as np
import pandas as pd

from thermal_twin.identification import (
    calculate_metrics,
    evaluate_topology,
    fit_topology,
    initial_log_parameters,
    residual_measured_minus_estimated,
)
from thermal_twin.rc_core import simulate_open_loop
from thermal_twin.topologies import reference_model_bank


def test_residual_sign_and_bic_follow_the_frozen_convention() -> None:
    measured = np.array([2.0, 4.0, 8.0])
    estimated = np.array([1.0, 5.0, 6.0])
    residual = residual_measured_minus_estimated(measured, estimated)
    assert np.array_equal(residual, [1.0, -1.0, 2.0])
    metrics = calculate_metrics(measured, estimated, n_parameters=2)
    assert metrics.rss == 6.0
    assert np.isclose(metrics.rmse, np.sqrt(2.0))
    assert np.isclose(metrics.mae, 4.0 / 3.0)
    assert np.isclose(metrics.bic, 3 * np.log(2.0) + 2 * np.log(3.0))


def test_initialisation_matches_cell_55_for_four_r_three_c() -> None:
    topology = reference_model_bank()[15]
    expected = np.r_[np.log(np.full(4, 0.2)), np.log(np.full(3, 1e7)), np.log(1e-4)]
    assert np.array_equal(initial_log_parameters(topology), expected)


def test_open_loop_oracle_is_near_exact_and_l_bfgs_b_outcome_is_deterministic() -> None:
    topology = reference_model_bank()[0]
    true_theta = np.log([0.7, 30.0, 0.03])
    tout = np.linspace(5.0, 13.0, 96)
    q = 400.0 + 100.0 * np.sin(np.linspace(0.0, 8.0, 96))
    ideal_tin = simulate_open_loop(topology, tout, q, 3600.0, true_theta, 20.0)
    tin = ideal_tin + 1e-8 * np.cos(np.linspace(0.0, 4.0, 96))
    frame = pd.DataFrame({"Tin": tin, "Tout": tout, "Qhvac_W_A": q})
    oracle_fit = type("OracleFit", (), {"topology": topology, "parameters_log": true_theta, "n_parameters": 3})()
    oracle_evaluation = evaluate_topology(oracle_fit, frame)
    assert oracle_evaluation.metrics.rmse < 1e-8
    assert np.isfinite(oracle_evaluation.metrics.bic)
    first = fit_topology(topology, frame)
    second = fit_topology(topology, frame)
    assert np.array_equal(first.parameters_log, second.parameters_log)
    assert first.success == second.success
    first_evaluation = evaluate_topology(first, frame)
    second_evaluation = evaluate_topology(second, frame)
    assert np.array_equal(first_evaluation.prediction, second_evaluation.prediction)
    assert np.array_equal(first_evaluation.residual, tin - first_evaluation.prediction)
