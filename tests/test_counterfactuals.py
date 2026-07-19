"""Scenario arithmetic: exact tracking identity, real effects, honest limits."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from thermal_twin.counterfactuals import (
    SCENARIO_BANK,
    apply_scenario,
    scenario_applicability,
    scenario_effect,
    tracking_power,
)
from thermal_twin.multistart_impl import ORACLE_PHYSICAL_PARAMETERS_4R3C
from thermal_twin.fast_sim import simulate_open_loop_fast
from thermal_twin.topologies import STD_1R1C, STD_4R3C

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def hourly() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "processed" / "hourly_reference.csv",
                       parse_dates=["Date"]).set_index("Date")


@pytest.fixture(scope="module")
def twin_theta() -> np.ndarray:
    return np.log(np.asarray(ORACLE_PHYSICAL_PARAMETERS_4R3C, dtype=float))


def test_tracking_inversion_recovers_measured_power_when_nothing_changes(hourly, twin_theta) -> None:
    subset = hourly.iloc[:600]
    tout = subset["Tout"].to_numpy()
    q_measured = subset["Qhvac_W_A"].to_numpy()
    baseline = simulate_open_loop_fast(STD_4R3C, tout, q_measured, 3600.0, twin_theta,
                                       float(subset["Tin"].iloc[0]))
    recovered = tracking_power(STD_4R3C, twin_theta, tout, baseline)
    assert np.max(np.abs(recovered[:-1] - q_measured[:-1])) < 1e-4


def test_envelope_scenario_produces_a_real_saving_on_the_twin(hourly, twin_theta) -> None:
    scenario = next(item for item in SCENARIO_BANK if item.key == "enveloppe_x2")
    effect = scenario_effect(STD_4R3C, twin_theta, hourly, scenario)
    assert effect.applicable
    assert effect.delta_energy_pct is not None and effect.delta_energy_pct < -5.0
    assert effect.delta_tin_mean_c is not None and effect.delta_tin_mean_c > 0.1
    assert not effect.negligible_energy


def test_inertia_scenario_is_declared_unreadable_on_quasi_integrator_masses(hourly, twin_theta) -> None:
    scenario = next(item for item in SCENARIO_BANK if item.key == "inertie_x1_5")
    effect = scenario_effect(STD_4R3C, twin_theta, hourly, scenario)
    assert not effect.applicable
    assert "time constant" in effect.reason_if_not


def test_direct_path_scenario_collapses_onto_envelope_for_single_path_structures() -> None:
    scenario = next(item for item in SCENARIO_BANK if item.key == "fuites_directes_x2")
    applicable, reason = scenario_applicability(STD_1R1C, scenario)
    assert not applicable
    assert "identical to the envelope scenario" in reason


def test_apply_scenario_scales_only_targeted_parameters(twin_theta) -> None:
    scenario = next(item for item in SCENARIO_BANK if item.key == "fuites_directes_x2")
    modified = apply_scenario(STD_4R3C, twin_theta, scenario)
    # STD_4R3C outdoor edges: (node 2, R2) and (node 0, R3); only R3 is the direct path.
    assert np.isclose(modified[3] - twin_theta[3], np.log(2.0))
    assert np.isclose(modified[2], twin_theta[2])
    assert np.allclose(modified[4:], twin_theta[4:])
