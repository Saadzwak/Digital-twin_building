"""Frozen identification and metric protocol from notebook cell 55."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import OptimizeResult, minimize

from .rc_core import RCTopology, simulate_open_loop


DT_SECONDS = 3600.0
RESIDUAL_CONVENTION = "Tin_measured - Tin_estimated"


@dataclass(frozen=True)
class Metrics:
    """Metrics computed from the single, immutable residual convention."""

    n_observations: int
    n_parameters: int
    rmse: float
    mae: float
    rss: float
    aic: float
    bic: float
    residual_mean: float


@dataclass(frozen=True)
class FittedTopology:
    """The raw optimiser outcome and physical parameters, even if unsuccessful."""

    topology: RCTopology
    parameters_log: np.ndarray
    resistances: np.ndarray
    capacitances: np.ndarray
    alpha: float
    n_parameters: int
    success: bool
    status: int
    message: str
    nfev: int | None
    nit: int | None
    objective_mse: float


@dataclass(frozen=True)
class Evaluation:
    """Open-loop prediction, signed residual and reproducible scalar metrics."""

    prediction: np.ndarray
    residual: np.ndarray
    metrics: Metrics


def _series_values(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    required = ["Tin", "Tout", "Qhvac_W_A"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}.")
    tin = frame["Tin"].to_numpy(dtype=float)
    tout = frame["Tout"].to_numpy(dtype=float)
    q_hvac = frame["Qhvac_W_A"].to_numpy(dtype=float)
    if len(tin) == 0 or not (np.isfinite(tin).all() and np.isfinite(tout).all() and np.isfinite(q_hvac).all()):
        raise ValueError("Tin, Tout and Qhvac_W_A must be non-empty finite arrays.")
    return tin, tout, q_hvac


def residual_measured_minus_estimated(measured: Iterable[float], estimated: Iterable[float]) -> np.ndarray:
    """Return the only residual sign permitted anywhere in this project."""

    y = np.asarray(tuple(measured), dtype=float)
    y_hat = np.asarray(tuple(estimated), dtype=float)
    if y.shape != y_hat.shape or y.ndim != 1:
        raise ValueError("measured and estimated must be one-dimensional arrays of equal shape.")
    if not np.isfinite(y).all() or not np.isfinite(y_hat).all():
        raise ValueError("measured and estimated must be finite.")
    return y - y_hat


def calculate_metrics(
    measured: Iterable[float], estimated: Iterable[float], n_parameters: int
) -> Metrics:
    """Calculate notebook-equivalent RMSE/MAE/RSS/AIC/BIC from signed residuals."""

    if n_parameters < 0:
        raise ValueError("n_parameters cannot be negative.")
    residual = residual_measured_minus_estimated(measured, estimated)
    n_observations = len(residual)
    if n_observations == 0:
        raise ValueError("metrics require at least one observation.")
    rss = float(np.sum(residual**2))
    rmse = float(np.sqrt(np.mean(residual**2)))
    mae = float(np.mean(np.abs(residual)))
    # These are deliberately the cell-55 comparison formulae, not a claim that
    # an independent Gaussian likelihood has been fully specified.
    aic = float(n_observations * np.log(rss / n_observations) + 2 * n_parameters)
    bic = float(n_observations * np.log(rss / n_observations) + n_parameters * np.log(n_observations))
    return Metrics(
        n_observations=n_observations,
        n_parameters=n_parameters,
        rmse=rmse,
        mae=mae,
        rss=rss,
        aic=aic,
        bic=bic,
        residual_mean=float(np.mean(residual)),
    )


def initial_log_parameters(topology: RCTopology) -> np.ndarray:
    """Return exactly the reference initialisation from the notebook."""

    topology.validate()
    return np.concatenate(
        [
            np.log(np.full(topology.n_resistances, 0.2)),
            np.log(np.full(topology.n_capacitances, 1e7)),
            np.array([np.log(1e-4)]),
        ]
    )


def log_parameter_bounds(topology: RCTopology) -> list[tuple[float, float]]:
    """Return the unmodified bounds from notebook cell 55."""

    topology.validate()
    return [(-10.0, 5.0)] * topology.n_resistances + [(8.0, 25.0)] * topology.n_capacitances + [(-20.0, 2.0)]


def fit_topology(
    topology: RCTopology,
    train_frame: pd.DataFrame,
    dt_seconds: float = DT_SECONDS,
) -> FittedTopology:
    """Fit a topology with the reference L-BFGS-B call and no hidden tuning.

    There are deliberately no optimiser options, restarts, altered initial
    points or post-fit parameter adjustments.  Metrics remain usable even if
    the returned ``success`` flag is false.
    """

    tin, tout, q_hvac = _series_values(train_frame)
    x0 = initial_log_parameters(topology)
    bounds = log_parameter_bounds(topology)

    def loss(parameters_log: np.ndarray) -> float:
        estimated = simulate_open_loop(topology, tout, q_hvac, dt_seconds, parameters_log, tin[0])
        residual = residual_measured_minus_estimated(tin, estimated)
        return float(np.mean(residual**2))

    result: OptimizeResult = minimize(loss, x0, bounds=bounds, method="L-BFGS-B")
    theta = np.asarray(result.x, dtype=float)
    physical = np.exp(theta)
    n_resistances = topology.n_resistances
    n_capacitances = topology.n_capacitances
    return FittedTopology(
        topology=topology,
        parameters_log=theta,
        resistances=physical[:n_resistances],
        capacitances=physical[n_resistances : n_resistances + n_capacitances],
        alpha=float(physical[-1]),
        n_parameters=n_resistances + n_capacitances + 1,
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        nfev=int(result.nfev) if result.nfev is not None else None,
        nit=int(result.nit) if result.nit is not None else None,
        objective_mse=float(result.fun),
    )


def evaluate_topology(
    fitted: FittedTopology,
    frame: pd.DataFrame,
    dt_seconds: float = DT_SECONDS,
) -> Evaluation:
    """Evaluate a separately reset, open-loop period exactly as cell 55 does."""

    tin, tout, q_hvac = _series_values(frame)
    prediction = simulate_open_loop(
        fitted.topology, tout, q_hvac, dt_seconds, fitted.parameters_log, tin[0]
    )
    residual = residual_measured_minus_estimated(tin, prediction)
    return Evaluation(
        prediction=prediction,
        residual=residual,
        metrics=calculate_metrics(tin, prediction, fitted.n_parameters),
    )


def fit_to_serializable(fitted: FittedTopology) -> dict[str, object]:
    """Make a raw fit outcome safe to journal without hiding non-convergence."""

    return {
        "model": fitted.topology.name,
        "n_parameters": fitted.n_parameters,
        "resistances": fitted.resistances.tolist(),
        "capacitances": fitted.capacitances.tolist(),
        "alpha": fitted.alpha,
        "success": fitted.success,
        "status": fitted.status,
        "message": fitted.message,
        "nfev": fitted.nfev,
        "nit": fitted.nit,
        "objective_mse": fitted.objective_mse,
        "residual_convention": RESIDUAL_CONVENTION,
    }
