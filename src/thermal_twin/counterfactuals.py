"""Parameter-space interventions on the identified effective model.

Every scenario rescales identified parameters (never forcings), then reports
two conditional effects over the full measured year:

- free running: same measured HVAC power, what indoor temperature results;
- tracked setpoint: what HVAC power holds the baseline indoor trajectory,
  obtained by inverting the air-node row of the exact discrete update.

These are conditional model arithmetic on effective parameters.  They are
not causal guarantees about a physical retrofit, and the display layer must
keep saying so.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .fast_sim import simulate_open_loop_fast
from .rc_core import RCTopology, build_continuous_matrices, discretize_exact

# Below these magnitudes a scenario is reported as negligible instead of as a
# meaningless tiny number.
NEGLIGIBLE_DELTA_T_C = 0.05
NEGLIGIBLE_DELTA_ENERGY_FRACTION = 0.005


@dataclass(frozen=True)
class ScenarioDefinition:
    key: str
    title: str
    description: str
    resistance_scale_outdoor: float = 1.0
    resistance_scale_air_outdoor: float = 1.0
    capacitance_scale: float = 1.0


SCENARIO_BANK: tuple[ScenarioDefinition, ...] = (
    ScenarioDefinition(
        key="enveloppe_x1_5",
        title="Reinforced envelope (+50% resistance)",
        description="All resistances to the outdoors multiplied by 1.5.",
        resistance_scale_outdoor=1.5,
    ),
    ScenarioDefinition(
        key="enveloppe_x2",
        title="Strongly reinforced envelope (resistance doubled)",
        description="All resistances to the outdoors multiplied by 2.",
        resistance_scale_outdoor=2.0,
    ),
    ScenarioDefinition(
        key="fuites_directes_x2",
        title="Direct losses halved",
        description="The resistance of the direct indoor-to-outdoor path is doubled (infiltration, uncontrolled ventilation).",
        resistance_scale_air_outdoor=2.0,
    ),
    ScenarioDefinition(
        key="inertie_x1_5",
        title="Reinforced thermal mass (+50%)",
        description="All thermal capacities multiplied by 1.5.",
        capacitance_scale=1.5,
    ),
)


def air_outdoor_resistance_indices(topology: RCTopology) -> tuple[int, ...]:
    return tuple(index for node, index in topology.outdoor_edges if node == 0)


def outdoor_resistance_indices(topology: RCTopology) -> tuple[int, ...]:
    return tuple(index for _, index in topology.outdoor_edges)


MAX_READABLE_TIME_CONSTANT_HOURS = 8760.0


def scenario_applicability(
    topology: RCTopology,
    scenario: ScenarioDefinition,
    parameters_log: np.ndarray | None = None,
) -> tuple[bool, str]:
    """State plainly when a scenario cannot be distinguished on this structure."""

    if scenario.resistance_scale_air_outdoor != 1.0:
        air_edges = air_outdoor_resistance_indices(topology)
        if not air_edges:
            return False, "The selected structure has no separate direct indoor-to-outdoor path."
        if len(outdoor_resistance_indices(topology)) == len(air_edges):
            return (
                False,
                "On the selected structure, the direct path is the only path to the outdoors: "
                "this scenario would be identical to the envelope scenario.",
            )
    if scenario.capacitance_scale != 1.0 and parameters_log is not None:
        physical = np.exp(np.asarray(parameters_log, dtype=float))
        matrices = build_continuous_matrices(
            topology,
            physical[: topology.n_resistances],
            physical[topology.n_resistances : -1],
            float(physical[-1]),
        )
        eigenvalues = np.linalg.eigvals(matrices.A)
        real_parts = np.real(eigenvalues)
        active = real_parts[real_parts < -1e-30]
        if len(active) == 0:
            return False, "No readable dynamics on this calibration: the thermal-mass lever cannot be interpreted."
        slowest_hours = float(np.max(-1.0 / active) / 3600.0)
        if slowest_hours > MAX_READABLE_TIME_CONSTANT_HOURS:
            return (
                False,
                "The identified effective thermal mass has no physical reading on this calibration "
                f"(time constant ≈ {slowest_hours:,.0f} h, beyond one year): "
                "the simulated effect of a thermal-mass change would not be interpretable.",
            )
    return True, ""


def apply_scenario(topology: RCTopology, parameters_log: np.ndarray, scenario: ScenarioDefinition) -> np.ndarray:
    theta = np.asarray(parameters_log, dtype=float).copy()
    n_r = topology.n_resistances
    if scenario.resistance_scale_outdoor != 1.0:
        for index in outdoor_resistance_indices(topology):
            theta[index] += np.log(scenario.resistance_scale_outdoor)
    if scenario.resistance_scale_air_outdoor != 1.0:
        for index in air_outdoor_resistance_indices(topology):
            theta[index] += np.log(scenario.resistance_scale_air_outdoor)
    if scenario.capacitance_scale != 1.0:
        theta[n_r : n_r + topology.n_capacitances] += np.log(scenario.capacitance_scale)
    return theta


def tracking_power(
    topology: RCTopology,
    parameters_log: np.ndarray,
    tout: np.ndarray,
    target_tin: np.ndarray,
    dt_seconds: float = 3600.0,
) -> np.ndarray:
    """Invert the air-node row so the model holds ``target_tin`` exactly.

    Returns the HVAC power series (W, same convention as the measured input).
    Mass-node states evolve freely under the resulting input.
    """

    theta = np.asarray(parameters_log, dtype=float)
    physical = np.exp(theta)
    matrices = build_continuous_matrices(
        topology,
        physical[: topology.n_resistances],
        physical[topology.n_resistances : -1],
        float(physical[-1]),
    )
    discrete = discretize_exact(matrices, dt_seconds)
    n_steps = len(tout)
    if discrete.Bd_q[0] <= 0.0:
        raise ValueError("The air node does not receive the HVAC input; tracking inversion is impossible.")
    state = np.full(topology.n_nodes, float(target_tin[0]))
    power = np.empty(n_steps, dtype=float)
    power[-1] = 0.0
    for index in range(n_steps - 1):
        free_air = float(discrete.Ad[0, :] @ state) + float(discrete.Bd_out[0]) * tout[index]
        power[index] = (target_tin[index + 1] - free_air) / float(discrete.Bd_q[0])
        state = discrete.Ad @ state + discrete.Bd_out * tout[index] + discrete.Bd_q * power[index]
    return power


@dataclass(frozen=True)
class ScenarioEffect:
    key: str
    title: str
    description: str
    applicable: bool
    reason_if_not: str
    delta_tin_mean_c: float | None
    delta_tin_winter_c: float | None
    daily_swing_damping_pct: float | None
    delta_energy_kwh: float | None
    delta_energy_pct: float | None
    negative_power_fraction: float | None
    negligible_temperature: bool
    negligible_energy: bool


def _winter_mask(index: pd.DatetimeIndex) -> np.ndarray:
    return np.isin(index.month, (1, 2, 3, 11, 12))


def _daily_swing(series: pd.Series) -> float:
    daily = series.resample("1D")
    swing = (daily.max() - daily.min()).dropna()
    return float(swing.mean()) if len(swing) else float("nan")


def scenario_effect(
    topology: RCTopology,
    parameters_log: np.ndarray,
    hourly: pd.DataFrame,
    scenario: ScenarioDefinition,
    dt_seconds: float = 3600.0,
) -> ScenarioEffect:
    applicable, reason = scenario_applicability(topology, scenario, parameters_log)
    if not applicable:
        return ScenarioEffect(
            key=scenario.key, title=scenario.title, description=scenario.description,
            applicable=False, reason_if_not=reason,
            delta_tin_mean_c=None, delta_tin_winter_c=None, daily_swing_damping_pct=None,
            delta_energy_kwh=None, delta_energy_pct=None, negative_power_fraction=None,
            negligible_temperature=False, negligible_energy=False,
        )

    index = pd.DatetimeIndex(hourly.index)
    tout = hourly["Tout"].to_numpy(dtype=float)
    q_measured = hourly["Qhvac_W_A"].to_numpy(dtype=float)
    tin_first = float(hourly["Tin"].iloc[0])
    theta_base = np.asarray(parameters_log, dtype=float)
    theta_mod = apply_scenario(topology, theta_base, scenario)

    baseline = simulate_open_loop_fast(topology, tout, q_measured, dt_seconds, theta_base, tin_first)
    free_run = simulate_open_loop_fast(topology, tout, q_measured, dt_seconds, theta_mod, tin_first)
    delta = free_run - baseline
    winter = _winter_mask(index)
    delta_mean = float(np.mean(delta))
    delta_winter = float(np.mean(delta[winter])) if winter.any() else float("nan")

    swing_base = _daily_swing(pd.Series(baseline, index=index))
    swing_mod = _daily_swing(pd.Series(free_run, index=index))
    damping_pct = float((1.0 - swing_mod / swing_base) * 100.0) if swing_base > 0 else None

    required_power = tracking_power(topology, theta_mod, tout, baseline, dt_seconds)
    hours = dt_seconds / 3600.0
    baseline_energy_kwh = float(np.sum(q_measured[:-1]) * hours / 1000.0)
    required_energy_kwh = float(np.sum(required_power[:-1]) * hours / 1000.0)
    delta_energy_kwh = required_energy_kwh - baseline_energy_kwh
    delta_energy_pct = (delta_energy_kwh / baseline_energy_kwh * 100.0) if baseline_energy_kwh > 0 else None
    negative_fraction = float(np.mean(required_power[:-1] < 0.0))

    return ScenarioEffect(
        key=scenario.key, title=scenario.title, description=scenario.description,
        applicable=True, reason_if_not="",
        delta_tin_mean_c=delta_mean,
        delta_tin_winter_c=delta_winter,
        daily_swing_damping_pct=damping_pct,
        delta_energy_kwh=delta_energy_kwh,
        delta_energy_pct=delta_energy_pct,
        negative_power_fraction=negative_fraction,
        negligible_temperature=abs(delta_mean) < NEGLIGIBLE_DELTA_T_C,
        negligible_energy=(
            delta_energy_pct is not None and abs(delta_energy_pct) < NEGLIGIBLE_DELTA_ENERGY_FRACTION * 100.0
        ),
    )


def scenario_dispersion(
    topology: RCTopology,
    parameter_vectors: tuple[np.ndarray, ...],
    hourly: pd.DataFrame,
    scenario: ScenarioDefinition,
    dt_seconds: float = 3600.0,
) -> dict[str, object]:
    """Empirical spread of scenario effects across admissible start vectors.

    The spread is an inter-start empirical range, not a statistical
    confidence interval; the display layer keeps that wording.
    """

    energies: list[float] = []
    temperatures: list[float] = []
    for theta in parameter_vectors:
        effect = scenario_effect(topology, theta, hourly, scenario, dt_seconds)
        if not effect.applicable:
            continue
        if effect.delta_energy_pct is not None:
            energies.append(effect.delta_energy_pct)
        if effect.delta_tin_mean_c is not None:
            temperatures.append(effect.delta_tin_mean_c)
    def _spread(values: list[float]) -> dict[str, float] | None:
        if not values:
            return None
        array = np.asarray(values, dtype=float)
        return {
            "median": float(np.median(array)),
            "q05": float(np.quantile(array, 0.05)),
            "q95": float(np.quantile(array, 0.95)),
            "n_vectors": int(len(array)),
        }
    return {
        "delta_energy_pct": _spread(energies),
        "delta_tin_mean_c": _spread(temperatures),
        "interpretation": "empirical range across starts, not a statistical confidence interval",
    }
