"""The accelerated simulator must match the frozen loop on every topology."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from thermal_twin.fast_sim import simulate_open_loop_fast
from thermal_twin.identification import initial_log_parameters, log_parameter_bounds
from thermal_twin.rc_core import simulate_open_loop
from thermal_twin.topologies import reference_model_bank

ROOT = Path(__file__).resolve().parents[1]
TOLERANCE_C = 1e-7


@pytest.fixture(scope="module")
def short_real_series() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    hourly = pd.read_csv(ROOT / "data" / "processed" / "hourly_reference.csv",
                         parse_dates=["Date"]).set_index("Date").iloc[:500]
    return (hourly["Tin"].to_numpy(), hourly["Tout"].to_numpy(), hourly["Qhvac_W_A"].to_numpy())


def test_fast_simulator_matches_reference_loop_on_all_topologies(short_real_series) -> None:
    tin, tout, q = short_real_series
    rng = np.random.default_rng(20260719)
    for topology in reference_model_bank():
        bounds = np.asarray(log_parameter_bounds(topology), dtype=float)
        candidates = [initial_log_parameters(topology)]
        for _ in range(2):
            candidates.append(rng.uniform(bounds[:, 0], bounds[:, 1]))
        for theta in candidates:
            reference = simulate_open_loop(topology, tout, q, 3600.0, theta, tin[0])
            fast = simulate_open_loop_fast(topology, tout, q, 3600.0, np.asarray(theta), tin[0])
            assert np.max(np.abs(reference - fast)) < TOLERANCE_C, topology.name
