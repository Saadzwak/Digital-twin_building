from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import expm

from thermal_twin.rc_core import build_continuous_matrices, discretize_exact, simulate_open_loop
from thermal_twin.topologies import STD_2R1C, STD_4R3C, reference_model_bank


def test_all_19_topologies_are_valid_and_labels_are_preserved() -> None:
    bank = reference_model_bank()
    assert len(bank) == 19
    assert [topology.name for topology in bank] == [
        "LADDER_1R1C", "LADDER_2R2C", "LADDER_3R3C", "LADDER_4R4C", "LADDER_5R5C",
        "LADDER_6R6C", "LADDER_7R7C", "LADDER_8R8C", "LADDER_9R9C", "LADDER_10R10C",
        "STD_1R1C", "STD_2R1C_parallel_losses", "STD_2R2C_air_mass", "STD_3R2C_air_shunt",
        "STD_3R3C_two_masses_series", "STD_4R3C_two_masses_plus_air_shunt",
        "STD_5R3C_air_shunt_mid_shunt", "STD_6R4C_three_masses_plus_shunts",
        "STD_7R5C_four_masses_plus_shunts",
    ]
    for topology in bank:
        topology.validate()


def test_four_r_three_c_matches_the_frozen_matrix_oracle() -> None:
    matrices = build_continuous_matrices(STD_4R3C, [2.0, 4.0, 5.0, 10.0], [10.0, 20.0, 40.0], 0.5)
    assert np.allclose(matrices.K, [[0.6, -0.5, 0.0], [-0.5, 0.75, -0.25], [0.0, -0.25, 0.45]])
    assert np.allclose(matrices.k_out, [0.1, 0.0, 0.2])
    assert np.allclose(matrices.A, [[-0.06, 0.05, 0.0], [0.025, -0.0375, 0.0125], [0.0, 0.00625, -0.01125]])
    assert np.allclose(matrices.b_out, [0.01, 0.0, 0.005])
    assert np.allclose(matrices.b_q, [0.05, 0.0, 0.0])
    assert np.allclose(matrices.K @ np.ones(3), matrices.k_out)
    assert np.allclose(matrices.A @ np.ones(3) + matrices.b_out, np.zeros(3))


def test_parallel_outdoor_resistances_add_their_conductances() -> None:
    matrices = build_continuous_matrices(STD_2R1C, [2.0, 4.0], [10.0], 0.5)
    assert np.allclose(matrices.K, [[0.75]])
    assert np.allclose(matrices.k_out, [0.75])


def test_one_r_one_c_closed_form_and_input_indexing() -> None:
    topology = reference_model_bank()[0]
    theta = np.log([2.0, 5.0, 0.4])
    matrices = build_continuous_matrices(topology, [2.0], [5.0], 0.4)
    discrete = discretize_exact(matrices, 3.0)
    decay = np.exp(-0.3)
    assert np.allclose(discrete.Ad, [[decay]], rtol=1e-12, atol=1e-12)
    assert np.allclose(discrete.Bd_out, [1.0 - decay], rtol=1e-12, atol=1e-12)
    assert np.allclose(discrete.Bd_q, [0.4 * 2.0 * (1.0 - decay)], rtol=1e-12, atol=1e-12)
    prediction = simulate_open_loop(topology, [0.0, 0.0, 0.0], [3.0, 0.0, 0.0], 3.0, theta, 0.0)
    assert np.allclose(prediction, [0.0, discrete.Bd_q[0] * 3.0, decay * discrete.Bd_q[0] * 3.0])


def test_augmented_zoh_matches_independent_matrix_formula_and_semigroup() -> None:
    matrices = build_continuous_matrices(STD_4R3C, [2.0, 4.0, 5.0, 10.0], [10.0, 20.0, 40.0], 0.5)
    one = discretize_exact(matrices, 3.0)
    two = discretize_exact(matrices, 6.0)
    expected_ad = expm(matrices.A * 3.0)
    expected_b = np.linalg.solve(matrices.A, (expected_ad - np.eye(3)) @ np.column_stack([matrices.b_out, matrices.b_q]))
    assert np.allclose(one.Ad, expected_ad, rtol=1e-11, atol=1e-12)
    assert np.allclose(np.column_stack([one.Bd_out, one.Bd_q]), expected_b, rtol=1e-11, atol=1e-12)
    assert np.allclose(two.Ad, one.Ad @ one.Ad, rtol=1e-11, atol=1e-12)
    assert np.allclose(np.column_stack([two.Bd_out, two.Bd_q]), one.Ad @ np.column_stack([one.Bd_out, one.Bd_q]) + np.column_stack([one.Bd_out, one.Bd_q]), rtol=1e-11, atol=1e-12)


def test_real_hourly_data_smoke_is_finite_open_loop_and_deterministic() -> None:
    root = Path(__file__).resolve().parents[1]
    data = pd.read_csv(root / "data" / "processed" / "hourly_reference.csv")
    theta = np.concatenate([np.log(np.full(4, 0.2)), np.log(np.full(3, 1e7)), [np.log(1e-4)]])
    first = simulate_open_loop(STD_4R3C, data["Tout"], data["Qhvac_W_A"], 3600.0, theta, float(data["Tin"].iloc[0]))
    second = simulate_open_loop(STD_4R3C, data["Tout"], data["Qhvac_W_A"], 3600.0, theta, float(data["Tin"].iloc[0]))
    assert first.shape == (8604,)
    assert np.isfinite(first).all()
    assert first[0] == data["Tin"].iloc[0]
    assert np.array_equal(first, second)
