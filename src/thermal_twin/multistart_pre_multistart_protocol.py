"""Uniform, deterministic multi-start identification for the frozen RC protocol.

This module changes only initial points.  Bounds, simulator, exact ZOH,
objective, L-BFGS-B method, tolerances and iteration defaults remain identical
to notebook cell 55.  Selection is *only* minimum train MSE.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from scipy.optimize import OptimizeResult, minimize

from .identification import (
    DT_SECONDS,
    Evaluation,
    FittedTopology,
    calculate_metrics,
    evaluate_topology,
    initial_log_parameters,
    log_parameter_bounds,
    residual_measured_minus_estimated,
)
from .rc_core import RCTopology, simulate_open_loop
from .reference_ingestion import split_reference_months
from .reproduction import NOTEBOOK_REFERENCE
from .topologies import STD_4R3C, reference_model_bank


MULTISTART_COUNT = 8
MULTISTART_SEED = 20260718
ORACLE_PHYSICAL_PARAMETERS_4R3C = np.array(
    [
        5.13956342e-04,
        2.87774378,
        1.10887673e-01,
        4.51489350e-03,
        1.74260153e10,
        2.98095799e3,
        6.34499651e10,
        3.6386052387,
    ],
    dtype=float,
)


@dataclass(frozen=True)
class MultiStartConfig:
    n_starts: int = MULTISTART_COUNT
    seed: int = MULTISTART_SEED
    dt_seconds: float = DT_SECONDS

    def __post_init__(self) -> None:
        if self.n_starts < 2:
            raise ValueError("Multi-start requires the notebook start plus at least one random start.")


@dataclass(frozen=True)
class StartOutcome:
    model: str
    model_index: int
    start_id: int
    start_kind: str
    start_seed: int | None
    initial_parameters_log: tuple[float, ...]
    final_parameters_log: tuple[float, ...] | None
    fit_success: bool
    fit_status: int | None
    fit_message: str
    nfev: int | None
    nit: int | None
    train_mse: float | None
    train_rmse: float | None
    validation_rmse: float | None
    validation_bic: float | None
    test_rmse: float | None
    error: str | None
    selected_by_train_mse: bool = False


@dataclass(frozen=True)
class BasinSummary:
    model: str
    model_index: int
    n_starts: int
    n_finite_train_runs: int
    n_successful: int
    selected_start_id: int | None
    selected_train_mse: float | None
    train_mse_median: float | None
    train_mse_max: float | None
    relative_train_mse_spread: float | None
    objective_basin_count: int
    endpoint_log_iqr_median: float | None
    identification_confidence: str
    confidence_reason: str


@dataclass(frozen=True)
class SelectedModel:
    model: str
    model_index: int
    selected_start_id: int
    train_mse: float
    validation_rmse: float
    validation_bic: float
    test_rmse: float
    fit_success: bool
    duplicate_of: str | None


def _frame_values(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tin = frame["Tin"].to_numpy(dtype=float)
    tout = frame["Tout"].to_numpy(dtype=float)
    q_hvac = frame["Qhvac_W_A"].to_numpy(dtype=float)
    if len(tin) == 0 or not (np.isfinite(tin).all() and np.isfinite(tout).all() and np.isfinite(q_hvac).all()):
        raise ValueError("Training frame must contain finite Tin, Tout and Qhvac_W_A values.")
    return tin, tout, q_hvac


def deterministic_start(
    topology: RCTopology,
    model_index: int,
    start_id: int,
    config: MultiStartConfig,
) -> tuple[np.ndarray, str, int | None]:
    """Return notebook start first, then log-uniform random points in published bounds."""

    if start_id < 1 or start_id > config.n_starts:
        raise ValueError("start_id is outside the configured common multi-start count.")
    if start_id == 1:
        return initial_log_parameters(topology), "notebook_initialization", None
    # A per-model/start child seed makes draws deterministic even when shards
    # execute in parallel or in a different order.
    child_seed = int(np.random.SeedSequence([config.seed, model_index, start_id]).generate_state(1)[0])
    rng = np.random.default_rng(child_seed)
    bounds = np.asarray(log_parameter_bounds(topology), dtype=float)
    return rng.uniform(bounds[:, 0], bounds[:, 1]), "log_uniform_within_published_bounds", child_seed


def fit_from_initial_parameters(
    topology: RCTopology,
    train_frame: pd.DataFrame,
    parameters_log_initial: Iterable[float],
    dt_seconds: float = DT_SECONDS,
) -> tuple[FittedTopology, Evaluation]:
    """One unmodified notebook L-BFGS-B call from a supplied allowed start."""

    tin, tout, q_hvac = _frame_values(train_frame)
    initial = np.asarray(tuple(parameters_log_initial), dtype=float)
    expected_size = topology.n_resistances + topology.n_capacitances + 1
    if initial.shape != (expected_size,) or not np.isfinite(initial).all():
        raise ValueError("Initial log parameter vector has invalid shape or values.")

    def loss(parameters_log: np.ndarray) -> float:
        estimated = simulate_open_loop(topology, tout, q_hvac, dt_seconds, parameters_log, tin[0])
        residual = residual_measured_minus_estimated(tin, estimated)
        return float(np.mean(residual**2))

    # No options are passed: this is intentionally the same optimizer call as
    # notebook cell 55.  Multi-start changes initial points only.
    result: OptimizeResult = minimize(loss, initial, bounds=log_parameter_bounds(topology), method="L-BFGS-B")
    theta = np.asarray(result.x, dtype=float)
    physical = np.exp(theta)
    fitted = FittedTopology(
        topology=topology,
        parameters_log=theta,
        resistances=physical[: topology.n_resistances],
        capacitances=physical[topology.n_resistances : topology.n_resistances + topology.n_capacitances],
        alpha=float(physical[-1]),
        n_parameters=expected_size,
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        nfev=int(result.nfev) if result.nfev is not None else None,
        nit=int(result.nit) if result.nit is not None else None,
        objective_mse=float(result.fun),
    )
    train_evaluation = evaluate_topology(fitted, train_frame, dt_seconds)
    return fitted, train_evaluation


def run_model_multistart(
    topology: RCTopology,
    model_index: int,
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    config: MultiStartConfig,
) -> tuple[list[StartOutcome], SelectedModel | None, BasinSummary]:
    """Execute all starts uniformly and select exclusively by train MSE."""

    outcomes: list[StartOutcome] = []
    fitted_by_start: dict[int, FittedTopology] = {}
    for start_id in range(1, config.n_starts + 1):
        initial, kind, child_seed = deterministic_start(topology, model_index, start_id, config)
        try:
            fitted, train_eval = fit_from_initial_parameters(topology, train, initial, config.dt_seconds)
            # Validation/test are evaluated only for journaled dispersion.  They
            # are not read by the selection expression below.
            validation_eval = evaluate_topology(fitted, validation, config.dt_seconds)
            test_eval = evaluate_topology(fitted, test, config.dt_seconds)
            outcomes.append(
                StartOutcome(
                    model=topology.name,
                    model_index=model_index,
                    start_id=start_id,
                    start_kind=kind,
                    start_seed=child_seed,
                    initial_parameters_log=tuple(float(value) for value in initial),
                    final_parameters_log=tuple(float(value) for value in fitted.parameters_log),
                    fit_success=fitted.success,
                    fit_status=fitted.status,
                    fit_message=fitted.message,
                    nfev=fitted.nfev,
                    nit=fitted.nit,
                    train_mse=train_eval.metrics.rss / train_eval.metrics.n_observations,
                    train_rmse=train_eval.metrics.rmse,
                    validation_rmse=validation_eval.metrics.rmse,
                    validation_bic=validation_eval.metrics.bic,
                    test_rmse=test_eval.metrics.rmse,
                    error=None,
                )
            )
            fitted_by_start[start_id] = fitted
        except Exception as error:  # Preserve an unusable start rather than silently dropping it.
            outcomes.append(
                StartOutcome(
                    model=topology.name,
                    model_index=model_index,
                    start_id=start_id,
                    start_kind=kind,
                    start_seed=child_seed,
                    initial_parameters_log=tuple(float(value) for value in initial),
                    final_parameters_log=None,
                    fit_success=False,
                    fit_status=None,
                    fit_message="exception during unmodified optimizer run",
                    nfev=None,
                    nit=None,
                    train_mse=None,
                    train_rmse=None,
                    validation_rmse=None,
                    validation_bic=None,
                    test_rmse=None,
                    error=f"{type(error).__name__}: {error}",
                )
            )

    finite = [outcome for outcome in outcomes if outcome.train_mse is not None and np.isfinite(outcome.train_mse)]
    selected: SelectedModel | None = None
    if finite:
        # This is the sole selection rule.  Stable start id is the tie-breaker.
        winner = min(finite, key=lambda outcome: (float(outcome.train_mse), outcome.start_id))
        outcomes = [
            StartOutcome(**{**asdict(outcome), "selected_by_train_mse": outcome.start_id == winner.start_id})
            for outcome in outcomes
        ]
        topology_duplicate = topology.duplicate_of
        selected = SelectedModel(
            model=topology.name,
            model_index=model_index,
            selected_start_id=winner.start_id,
            train_mse=float(winner.train_mse),
            validation_rmse=float(winner.validation_rmse),
            validation_bic=float(winner.validation_bic),
            test_rmse=float(winner.test_rmse),
            fit_success=winner.fit_success,
            duplicate_of=topology_duplicate,
        )
    summary = summarize_basins(topology.name, model_index, outcomes, config.n_starts)
    return outcomes, selected, summary


def summarize_basins(
    model: str, model_index: int, outcomes: Sequence[StartOutcome], n_starts: int) -> BasinSummary:
    """Describe objective/end-point dispersion without presenting it as a probability."""

    finite = [outcome for outcome in outcomes if outcome.train_mse is not None and np.isfinite(outcome.train_mse)]
    successful = [outcome for outcome in outcomes if outcome.fit_success]
    if not finite:
        return BasinSummary(
            model, model_index, n_starts, 0, len(successful), None, None, None, None, None, 0, None,
            "inconclusive", "No finite train objective was obtained from the common start protocol.",
        )
    mse = np.array([float(outcome.train_mse) for outcome in finite])
    sorted_mse = np.sort(mse)
    basin_count = 1
    previous = sorted_mse[0]
    for value in sorted_mse[1:]:
        if abs(value - previous) > max(1e-9, 1e-4 * max(abs(previous), 1.0)):
            basin_count += 1
        previous = value
    endpoints = np.array([outcome.final_parameters_log for outcome in finite if outcome.final_parameters_log is not None], dtype=float)
    endpoint_iqr = float(np.median(np.subtract(*np.percentile(endpoints, [75, 25], axis=0)))) if len(endpoints) else None
    selected = next((outcome for outcome in outcomes if outcome.selected_by_train_mse), None)
    spread = float((np.max(mse) - np.min(mse)) / max(abs(np.min(mse)), 1e-12))
    if len(successful) / n_starts < 0.75:
        confidence, reason = "inconclusive", "Too many starts failed or produced no finite objective."
    elif basin_count > 1 or spread > 1e-3:
        confidence, reason = "sensitive_to_initialization", "Multiple train-objective basins or material train-MSE spread were observed."
    else:
        confidence, reason = "stable_over_sampled_starts", "Sampled starts converged to one near-equivalent train-objective basin."
    return BasinSummary(
        model=model,
        model_index=model_index,
        n_starts=n_starts,
        n_finite_train_runs=len(finite),
        n_successful=len(successful),
        selected_start_id=selected.start_id if selected else None,
        selected_train_mse=float(np.min(mse)),
        train_mse_median=float(np.median(mse)),
        train_mse_max=float(np.max(mse)),
        relative_train_mse_spread=spread,
        objective_basin_count=basin_count,
        endpoint_log_iqr_median=endpoint_iqr,
        identification_confidence=confidence,
        confidence_reason=reason,
    )


def run_multistart_shard(
    hourly: pd.DataFrame,
    model_indices: Iterable[int],
    config: MultiStartConfig,
) -> dict[str, object]:
    """Run a named subset; intended for deterministic parallel shards only."""

    splits = split_reference_months(hourly)
    bank = reference_model_bank()
    all_outcomes: list[StartOutcome] = []
    selected: list[SelectedModel] = []
    summaries: list[BasinSummary] = []
    for index in model_indices:
        if not 0 <= index < len(bank):
            raise ValueError(f"Unknown model index {index}.")
        outcomes, winner, summary = run_model_multistart(
            bank[index], index, splits["train"], splits["validation"], splits["test"], config
        )
        all_outcomes.extend(outcomes)
        if winner is not None:
            selected.append(winner)
        summaries.append(summary)
    return {
        "config": asdict(config),
        "model_indices": list(model_indices),
        "outcomes": [asdict(outcome) for outcome in all_outcomes],
        "selected": [asdict(item) for item in selected],
        "basin_summaries": [asdict(summary) for summary in summaries],
    }


def write_shard(path: Path | str, shard: dict[str, object]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(shard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def load_shards(paths: Iterable[Path | str]) -> dict[str, object]:
    """Merge shards and assert one uniform protocol and exactly one run per start."""

    shards = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
    if not shards:
        raise ValueError("At least one multi-start shard is required.")
    configurations = {json.dumps(shard["config"], sort_keys=True) for shard in shards}
    if len(configurations) != 1:
        raise ValueError("Shard configurations differ; uniform multi-start protocol is violated.")
    outcomes = [outcome for shard in shards for outcome in shard["outcomes"]]
    selected = [item for shard in shards for item in shard["selected"]]
    summaries = [item for shard in shards for item in shard["basin_summaries"]]
    indices = [index for shard in shards for index in shard["model_indices"]]
    if sorted(indices) != list(range(19)) or len(set(indices)) != 19:
        raise ValueError("Shards must cover each of the 19 fixed model labels exactly once.")
    config = json.loads(next(iter(configurations)))
    if len(outcomes) != 19 * int(config["n_starts"]):
        raise ValueError("Not every model received the same configured number of starts.")
    return {"config": config, "outcomes": outcomes, "selected": selected, "basin_summaries": summaries}


def notebook_parameter_oracle(hourly: pd.DataFrame) -> dict[str, object]:
    """Independent executable oracle; it never supplies an optimizer start."""

    splits = split_reference_months(hourly)
    theta = np.log(ORACLE_PHYSICAL_PARAMETERS_4R3C)
    fitted = FittedTopology(
        topology=STD_4R3C,
        parameters_log=theta,
        resistances=ORACLE_PHYSICAL_PARAMETERS_4R3C[:4],
        capacitances=ORACLE_PHYSICAL_PARAMETERS_4R3C[4:7],
        alpha=float(ORACLE_PHYSICAL_PARAMETERS_4R3C[-1]),
        n_parameters=8,
        success=True,
        status=0,
        message="printed notebook parameter oracle; never an optimizer initialization",
        nfev=None,
        nit=None,
        objective_mse=float("nan"),
    )
    validation = evaluate_topology(fitted, splits["validation"]).metrics
    testing = evaluate_topology(fitted, splits["test"]).metrics
    passed = (
        abs(validation.rmse - 4.682382) <= 5e-7
        and abs(validation.bic - 4578.578337) <= 3e-6
        and abs(testing.rmse - 0.857599) <= 5e-7
    )
    return {
        "passed": passed,
        "validation_rmse": validation.rmse,
        "validation_bic": validation.bic,
        "test_rmse": testing.rmse,
        "tolerance": {"rmse": 5e-7, "bic": 3e-6},
        "purpose": "post-fit regression oracle only; never a multi-start initialization or selection input",
    }


def revised_verdict(merged: dict[str, object], oracle: dict[str, object]) -> dict[str, object]:
    """Apply the user-authorized A/B validation rule exactly and transparently."""

    selected = sorted(merged["selected"], key=lambda row: row["validation_bic"])
    summaries = merged["basin_summaries"]
    std4 = next(row for row in selected if row["model"] == STD_4R3C.name)
    next_best = next(row for row in selected if row["model"] != STD_4R3C.name)
    bic_gap = float(next_best["validation_bic"] - std4["validation_bic"])
    criterion_a = bool(selected[0]["model"] == STD_4R3C.name and bic_gap >= 2.0)
    uniform = len(merged["outcomes"]) == 19 * int(merged["config"]["n_starts"])
    dispersion_documented = len(summaries) == 19
    criterion_b = bool((not criterion_a) and oracle["passed"] and uniform and dispersion_documented)
    verdict_kind = "A" if criterion_a else "B" if criterion_b else "FAILED"
    validated = verdict_kind in {"A", "B"}
    sensitivity = {
        summary["model"]: summary["identification_confidence"]
        for summary in summaries
    }
    return {
        "protocol": "uniform_multistart_notebook_cell_55",
        "validated": validated,
        "verdict": verdict_kind,
        "criterion_a": {
            "passed": criterion_a,
            "definition": "STD_4R3C has the lowest validation BIC among train-MSE-selected starts and a >=2 BIC gap to second place.",
            "std_4r3c_validation_bic": std4["validation_bic"],
            "next_best_model": next_best["model"],
            "bic_gap_to_next": bic_gap,
        },
        "criterion_b": {
            "passed": criterion_b,
            "definition": "Oracle passes; all 19 structures use the identical logged start protocol; basin dispersion is recorded.",
            "oracle_passed": oracle["passed"],
            "uniform_protocol": uniform,
            "dispersion_documented": dispersion_documented,
        },
        "config": merged["config"],
        "selection_rule": "Minimum train MSE only; validation and test were never used in selection.",
        "residual_convention": "Tin_measured - Tin_estimated",
        "sensitivity_banner_required": verdict_kind == "B",
        "sensitivity_by_structure": sensitivity,
        "conclusion": (
            "VALIDATED_MULTISTART_ARTICLE_RANKING" if verdict_kind == "A" else
            "VALIDATED_INITIALIZATION_SENSITIVE" if verdict_kind == "B" else
            "FAILED_MULTISTART_PROTOCOL"
        ),
    }


def write_multistart_artifacts(
    project_root: Path | str,
    merged: dict[str, object],
    oracle: dict[str, object],
    verdict: dict[str, object],
) -> dict[str, Path]:
    """Persist all starts, selected starts, basin dispersion and revised verdict."""

    root = Path(project_root).resolve()
    run_dir = root / "runs" / "m4"
    multi_dir = run_dir / "multistart"
    multi_dir.mkdir(parents=True, exist_ok=True)
    old_verdict = run_dir / "verdict.json"
    backup = run_dir / "single_start_verdict.json"
    if old_verdict.is_file() and not backup.is_file():
        shutil.copy2(old_verdict, backup)
    all_path = multi_dir / "all_starts.json"
    selected_path = multi_dir / "selected_by_train_mse.csv"
    basin_path = multi_dir / "basin_dispersion.csv"
    oracle_path = multi_dir / "notebook_parameter_oracle.json"
    verdict_path = run_dir / "verdict.json"
    all_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(merged["selected"]).sort_values("validation_bic").to_csv(selected_path, index=False)
    pd.DataFrame(merged["basin_summaries"]).sort_values("model_index").to_csv(basin_path, index=False)
    oracle_path.write_text(json.dumps(oracle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verdict_path.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "all_starts": all_path,
        "selected": selected_path,
        "basin_dispersion": basin_path,
        "oracle": oracle_path,
        "verdict": verdict_path,
        "single_start_backup": backup,
    }
