"""Owner-facing translation of effective-model quantities.

Surface wording never uses identification jargon; every number keeps its
uncertainty and its run source.  When an indicator has no physically
readable value on the current parameters, the card says so instead of
printing a large meaningless number.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .fast_sim import simulate_open_loop_fast
from .rc_core import RCTopology

# Words that must never appear in surface (level-1) strings; the technical
# expander is exempt.  Guarded by tests.
SURFACE_FORBIDDEN_TERMS: tuple[str, ...] = (
    "BIC", "RMSE", "L-BFGS-B", "MSE", "topology", "identifiability",
    "initialization", "log-space", "multi-start", "multistart", "oracle",
)

RELIABILITY_SURFACE_TEXT = (
    "Diagnostic reliability: acceptable, with caveats. The numerical calibration depends on its starting point; "
    "every range shown covers that variability. The full methodological detail is at the bottom of the page."
)

CANNOT_DISTINGUISH_TEXT = (
    "What the model cannot distinguish: a single indoor temperature is measured, "
    "so individual walls, facades or glazing are not separable. The levels shown "
    "are whole-building properties."
)


@dataclass(frozen=True)
class HeatLossLevel:
    ua_w_per_k: float
    direct_path_share: float | None
    physically_readable: bool


def effective_heat_loss(topology: RCTopology, resistances: np.ndarray, alpha: float) -> HeatLossLevel:
    """Whole-building effective heat-loss level in real W/K.

    The identified network works in scaled heat units (``Q = alpha * P``);
    dividing the outdoor conductance sum by ``alpha`` converts back to W/K.
    A level below 1 W/K for an occupied building block means the calibration
    landed on a flywheel-like solution with no envelope reading.
    """

    total = 0.0
    direct = 0.0
    for node, r_index in topology.outdoor_edges:
        conductance = 1.0 / float(resistances[r_index])
        total += conductance
        if node == 0:
            direct += conductance
    ua = total / float(alpha)
    share = (direct / total) if total > 0 else None
    return HeatLossLevel(
        ua_w_per_k=ua,
        direct_path_share=share,
        physically_readable=bool(1.0 <= ua <= 100000.0),
    )


def response_time_hours(
    topology: RCTopology,
    parameters_log: np.ndarray,
    step_power_w: float = 1000.0,
    horizon_hours: int = 240,
    dt_seconds: float = 3600.0,
) -> float | None:
    """Time for indoor air to reach 63 % of its ``horizon_hours`` step response.

    Simulated, not read from a formula, because effective networks mix very
    fast and quasi-infinite modes.  ``None`` means no readable response inside
    the horizon.
    """

    tout = np.zeros(horizon_hours, dtype=float)
    power = np.full(horizon_hours, float(step_power_w))
    trajectory = simulate_open_loop_fast(topology, tout, power, dt_seconds, np.asarray(parameters_log, dtype=float), 0.0)
    final = float(trajectory[-1])
    if not np.isfinite(final) or abs(final) < 1e-9:
        return None
    target = 0.632 * final
    reached = np.nonzero(trajectory >= target)[0] if final > 0 else np.nonzero(trajectory <= target)[0]
    if len(reached) == 0:
        return None
    return float(reached[0] * dt_seconds / 3600.0)


def format_heat_loss_sentence(level: HeatLossLevel) -> str:
    if not level.physically_readable:
        return (
            "Heat-loss level: not readable on this calibration. The automated calibration converged on a "
            "solution with no physical reading of the envelope; see the methodological detail."
        )
    sentence = f"Effective heat-loss level: {level.ua_w_per_k:.0f} W per °C of indoor-outdoor difference."
    if level.direct_path_share is not None and level.direct_path_share >= 0.5:
        sentence += (
            f" About {level.direct_path_share * 100.0:.0f}% flows through a direct indoor-to-outdoor path "
            "(air renewal, infiltration), not through the building mass."
        )
    return sentence


def assert_surface_text_clean(text: str) -> None:
    """Raise when a surface string leaks identification jargon (test helper)."""

    lowered = text.lower()
    for term in SURFACE_FORBIDDEN_TERMS:
        if term.lower() in lowered:
            raise AssertionError(f"Surface text leaks technical term {term!r}: {text[:120]}")
