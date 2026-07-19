"""Uniform, deterministic multi-start identification for the frozen RC protocol.

Only the optimizer initial point changes from notebook cell 55.  Bounds,
exact ZOH simulation, objective, optimizer method and its default stopping
settings remain untouched.  A restart is retained solely by minimum train MSE.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
import scipy
from scipy.optimize import OptimizeResult, minimize

from .identification import (
    DT_SECONDS,
    Evaluation,
    FittedTopology,
    evaluate_topology,
    initial_log_parameters,
    log_parameter_bounds,
    residual_measured_minus_estimated,
)
from .rc_core import RCTopology, simulate_open_loop
from .reference_ingestion import split_reference_months
from .topologies import STD_4R3C, reference_model_bank


# Declared before the first M4 multi-start execution.  It gives every one of
# the nineteen fixed labels (including duplicates) one notebook point plus 31
# log-uniform points.  The count is deliberately not changed after observing a
# result for any label.
MULTISTART_COUNT = 32
# DOI suffix used only as a memorable fixed seed, never as a fitted value.
MULTISTART_SEED = 7096790
# A conventional "strong" BIC separation, declared before execution.
STRONG_BIC_GAP = 10.0
NEAR_BEST_TRAIN_FRACTION = 1e-4

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
    """The complete immutable initialisation protocol for one M4 run."""

    n_starts: int = MULTISTART_COUNT
    seed: int = MULTISTART_SEED
    dt_seconds: float = DT_SECONDS
    rng: str = "numpy.random.PCG64"

    def __post_init__(self) -> None:
        if self.n_starts < 2:
            raise ValueError("Multi-start requires notebook start plus a random start.")


@dataclass(frozen=True)
class StartOutcome:
    """One attempted optimizer trajectory, including a non-converged finite fit."""

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
    selection_reason: str = "not_selected"


@dataclass(frozen=True)
class BasinSummary:
    """Empirical variation across sampled starts; not a statistical CI."""

    model: str
    model_index: int
    n_starts: int
    n_finite_train_runs: int
    n_successful: int
    selected_start_id: int | None
    selected_train_mse: float | None
    train_mse_q05: float | None
    train_mse_median: float | None
    train_mse_q95: float | None
    train_mse_max: float | None
    validation_bic_q05: float | None
    validation_bic_median: float | None
    validation_bic_q95: float | None
    relative_train_mse_spread: float | None
    near_best_train_fraction: float | None
    objective_basin_count: int
    endpoint_log_iqr_median: float | None
    identification_confidence: str
    confidence_reason: str


@dataclass(frozen=True)
class SelectedModel:
    """The single in-topology restart retained by predeclared train MSE."""

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
    if len(tin) == 0 or not (
        np.isfinite(tin).all() and np.isfinite(tout).all() and np.isfinite(q_hvac).all()
    ):
        raise ValueError("Training frame must contain finite Tin, Tout and Qhvac_W_A values.")
    return tin, tout, q_hvac


def _profile_seed(topology: RCTopology, start_id: int, config: MultiStartConfig) -> np.random.SeedSequence:
    """Give topology profiles of equal dimension the same reproducible bank."""

    return np.random.SeedSequence(
        [config.seed, topology.n_resistances, topology.n_capacitances, start_id]
    )


def deterministic_start(
    topology: RCTopology,
    model_index: int,
    start_id: int,
    config: MultiStartConfig,
) -> tuple[np.ndarray, str, int | None]:
    """Return notebook start first, then a log-uniform published-bounds start.

    ``model_index`` remains in the public signature and journal so each fixed
    article label is distinct; the sampling deliberately depends on its
    parameter profile instead so duplicate profiles receive a fair common bank.
    """

    del model_index
    if start_id < 1 or start_id > config.n_starts:
        raise ValueError("start_id is outside the configured common multi-start count.")
    if start_id == 1:
        return initial_log_parameters(topology), "notebook_initialization", None
    child_sequence = _profile_seed(topology, start_id, config)
    child_seed = int(child_sequence.generate_state(1)[0])
    rng = np.random.Generator(np.random.PCG64(child_sequence))
    bounds = np.asarray(log_parameter_bounds(topology), dtype=float)
    return (
        rng.uniform(bounds[:, 0], bounds[:, 1]),
        "log_uniform_within_published_bounds",
        child_seed,
    )


def build_start_bank(
    topology: RCTopology, model_index: int, config: MultiStartConfig
) -> tuple[tuple[np.ndarray, str, int | None], ...]:
    """Materialize and journal every planned start before fitting any of them."""

    return tuple(
        deterministic_start(topology, model_index, start_id, config)
        for start_id in range(1, config.n_starts + 1)
    )


def fit_from_initial_parameters(
    topology: RCTopology,
    train_frame: pd.DataFrame,
    parameters_log_initial: Iterable[float],
    dt_seconds: float = DT_SECONDS,
) -> tuple[FittedTopology, Evaluation]:
    """One deliberately unmodified notebook L-BFGS-B call from an allowed start."""

    tin, tout, q_hvac = _frame_values(train_frame)
    initial = np.asarray(tuple(parameters_log_initial), dtype=float)
    expected_size = topology.n_resistances + topology.n_capacitances + 1
    if initial.shape != (expected_size,) or not np.isfinite(initial).all():
        raise ValueError("Initial log parameter vector has invalid shape or values.")

    def loss(parameters_log: np.ndarray) -> float:
        estimated = simulate_open_loop(topology, tout, q_hvac, dt_seconds, parameters_log, tin[0])
        residual = residual_measured_minus_estimated(tin, estimated)
        return float(np.mean(residual**2))

    # No tol, maxiter, options, jacobian or other optimizer argument is passed.
    result: OptimizeResult = minimize(
        loss, initial, bounds=log_parameter_bounds(topology), method="L-BFGS-B"
    )
    theta = np.asarray(result.x, dtype=float)
    physical = np.exp(theta)
    fitted = FittedTopology(
        topology=topology,
        parameters_log=theta,
        resistances=physical[: topology.n_resistances],
        capacitances=physical[
            topology.n_resistances : topology.n_resistances + topology.n_capacitances
        ],
        alpha=float(physical[-1]),
        n_parameters=expected_size,
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        nfev=int(result.nfev) if result.nfev is not None else None,
        nit=int(result.nit) if result.nit is not None else None,
        objective_mse=float(result.fun),
    )
    return fitted, evaluate_topology(fitted, train_frame, dt_seconds)


def run_model_multistart(
    topology: RCTopology,
    model_index: int,
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    config: MultiStartConfig,
) -> tuple[list[StartOutcome], SelectedModel | None, BasinSummary]:
    """Run the common bank and retain only the least train-MSE trajectory."""

    outcomes: list[StartOutcome] = []
    for start_id, (initial, kind, child_seed) in enumerate(
        build_start_bank(topology, model_index, config), start=1
    ):
        try:
            fitted, train_eval = fit_from_initial_parameters(topology, train, initial, config.dt_seconds)
            # These evaluations are journaled for diagnostics only.  The sole
            # selection expression below cannot read validation or test fields.
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
        except Exception as error:
            # A failed point stays visible and counts toward the fixed protocol.
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

    finite = [item for item in outcomes if item.train_mse is not None and np.isfinite(item.train_mse)]
    selected: SelectedModel | None = None
    if finite:
        # Deliberately includes success=False if its MSE is finite, as frozen.
        winner = min(finite, key=lambda item: (float(item.train_mse), item.start_id))
        outcomes = [
            StartOutcome(
                **{
                    **asdict(item),
                    "selected_by_train_mse": item.start_id == winner.start_id,
                    "selection_reason": (
                        "minimum_train_mse_then_lowest_start_id"
                        if item.start_id == winner.start_id
                        else "higher_train_mse_or_later_train_mse_tie"
                    ),
                }
            )
            for item in outcomes
        ]
        selected = SelectedModel(
            model=topology.name,
            model_index=model_index,
            selected_start_id=winner.start_id,
            train_mse=float(winner.train_mse),
            validation_rmse=float(winner.validation_rmse),
            validation_bic=float(winner.validation_bic),
            test_rmse=float(winner.test_rmse),
            fit_success=winner.fit_success,
            duplicate_of=topology.duplicate_of,
        )
    return outcomes, selected, summarize_basins(topology.name, model_index, outcomes, config.n_starts)


def _quantile(values: Sequence[float], probability: float) -> float | None:
    return float(np.quantile(np.asarray(values, dtype=float), probability)) if values else None


def summarize_basins(
    model: str, model_index: int, outcomes: Sequence[StartOutcome], n_starts: int
) -> BasinSummary:
    """Describe empirical sampled-start dispersion without calling it a CI."""

    finite = [item for item in outcomes if item.train_mse is not None and np.isfinite(item.train_mse)]
    successful = [item for item in outcomes if item.fit_success]
    if not finite:
        return BasinSummary(
            model, model_index, n_starts, 0, len(successful), None, None, None, None, None,
            None, None, None, None, None, 0, None, "inconclusive",
            "No finite train objective was obtained from the common start protocol.",
        )
    mse = np.asarray([float(item.train_mse) for item in finite], dtype=float)
    bic = [float(item.validation_bic) for item in finite if item.validation_bic is not None]
    sorted_mse = np.sort(mse)
    basin_count = 1
    previous = sorted_mse[0]
    for value in sorted_mse[1:]:
        if abs(value - previous) > max(1e-9, NEAR_BEST_TRAIN_FRACTION * max(abs(previous), 1.0)):
            basin_count += 1
        previous = value
    endpoints = np.asarray(
        [item.final_parameters_log for item in finite if item.final_parameters_log is not None], dtype=float
    )
    endpoint_iqr = (
        float(np.median(np.percentile(endpoints, 75, axis=0) - np.percentile(endpoints, 25, axis=0)))
        if len(endpoints)
        else None
    )
    selected = next((item for item in outcomes if item.selected_by_train_mse), None)
    minimum = float(np.min(mse))
    near_best = float(np.mean(mse <= minimum * (1.0 + NEAR_BEST_TRAIN_FRACTION)))
    spread = float((np.max(mse) - minimum) / max(abs(minimum), 1e-12))
    if len(successful) / n_starts < 0.75:
        confidence, reason = "inconclusive", "Too many starts failed or produced no finite objective."
    elif basin_count > 1 or spread > 1e-3:
        confidence, reason = (
            "sensitive_to_initialization",
            "Sampled starts reached multiple train-objective values or a material train-MSE spread.",
        )
    else:
        confidence, reason = (
            "stable_over_sampled_starts",
            "The sampled starts reached one near-equivalent train-objective value.",
        )
    return BasinSummary(
        model=model,
        model_index=model_index,
        n_starts=n_starts,
        n_finite_train_runs=len(finite),
        n_successful=len(successful),
        selected_start_id=selected.start_id if selected else None,
        selected_train_mse=minimum,
        train_mse_q05=_quantile(mse, 0.05),
        train_mse_median=_quantile(mse, 0.50),
        train_mse_q95=_quantile(mse, 0.95),
        train_mse_max=float(np.max(mse)),
        validation_bic_q05=_quantile(bic, 0.05),
        validation_bic_median=_quantile(bic, 0.50),
        validation_bic_q95=_quantile(bic, 0.95),
        relative_train_mse_spread=spread,
        near_best_train_fraction=near_best,
        objective_basin_count=basin_count,
        endpoint_log_iqr_median=endpoint_iqr,
        identification_confidence=confidence,
        confidence_reason=reason,
    )


def run_multistart_shard(
    hourly: pd.DataFrame, model_indices: Iterable[int], config: MultiStartConfig
) -> dict[str, object]:
    """Run a deterministic subset; safe to execute in independent shards."""

    indices = list(model_indices)
    splits = split_reference_months(hourly)
    bank = reference_model_bank()
    outcomes: list[StartOutcome] = []
    selected: list[SelectedModel] = []
    summaries: list[BasinSummary] = []
    for index in indices:
        if not 0 <= index < len(bank):
            raise ValueError(f"Unknown model index {index}.")
        attempts, winner, summary = run_model_multistart(
            bank[index], index, splits["train"], splits["validation"], splits["test"], config
        )
        outcomes.extend(attempts)
        if winner is not None:
            selected.append(winner)
        summaries.append(summary)
    return {
        "config": asdict(config),
        "model_indices": indices,
        "outcomes": [asdict(item) for item in outcomes],
        "selected": [asdict(item) for item in selected],
        "basin_summaries": [asdict(item) for item in summaries],
    }


def write_shard(path: Path | str, shard: dict[str, object]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(shard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def load_shards(paths: Iterable[Path | str]) -> dict[str, object]:
    """Merge shards and reject incomplete, duplicate, or nonuniform protocols."""

    shards = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
    if not shards:
        raise ValueError("At least one multi-start shard is required.")
    configurations = {json.dumps(shard["config"], sort_keys=True) for shard in shards}
    if len(configurations) != 1:
        raise ValueError("Shard configurations differ; uniform multi-start protocol is violated.")
    outcomes = [item for shard in shards for item in shard["outcomes"]]
    selected = [item for shard in shards for item in shard["selected"]]
    summaries = [item for shard in shards for item in shard["basin_summaries"]]
    indices = [index for shard in shards for index in shard["model_indices"]]
    if sorted(indices) != list(range(19)) or len(set(indices)) != 19:
        raise ValueError("Shards must cover every one of the 19 fixed labels exactly once.")
    config = json.loads(next(iter(configurations)))
    expected_attempts = 19 * int(config["n_starts"])
    pairs = {(item["model_index"], item["start_id"]) for item in outcomes}
    if len(outcomes) != expected_attempts or len(pairs) != expected_attempts:
        raise ValueError("Every label must receive each configured start exactly once.")
    if len(selected) != 19 or len(summaries) != 19:
        raise ValueError("Every label needs one train-selected fit and one dispersion summary.")
    return {"config": config, "outcomes": outcomes, "selected": selected, "basin_summaries": summaries}


def notebook_parameter_oracle(hourly: pd.DataFrame) -> dict[str, object]:
    """Run an independent post-fit regression oracle; it is never an optimizer start."""

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
    """Apply the user-authorized A/B M4 gate with predeclared A separation."""

    selected = sorted(merged["selected"], key=lambda row: row["validation_bic"])
    summaries = merged["basin_summaries"]
    std4 = next(row for row in selected if row["model"] == STD_4R3C.name)
    next_best = next(row for row in selected if row["model"] != STD_4R3C.name)
    bic_gap = float(next_best["validation_bic"] - std4["validation_bic"])
    criterion_a = bool(selected[0]["model"] == STD_4R3C.name and bic_gap >= STRONG_BIC_GAP)
    configured_starts = int(merged["config"]["n_starts"])
    observed_pairs = {(row["model_index"], row["start_id"]) for row in merged["outcomes"]}
    uniform = (
        len(merged["outcomes"]) == 19 * configured_starts
        and len(observed_pairs) == 19 * configured_starts
        and len(selected) == 19
    )
    dispersion_documented = len(summaries) == 19 and all(
        int(summary["n_starts"]) == configured_starts for summary in summaries
    )
    criterion_b = bool((not criterion_a) and oracle["passed"] and uniform and dispersion_documented)
    verdict_kind = "A" if criterion_a else "B" if criterion_b else "FAILED"
    sensitivity = {summary["model"]: summary["identification_confidence"] for summary in summaries}
    return {
        "protocol": "uniform_multistart_notebook_cell_55",
        "validated": verdict_kind in {"A", "B"},
        "validation_route": verdict_kind,
        "verdict": verdict_kind,
        "criterion_a": {
            "passed": criterion_a,
            "definition": "STD_4R3C has the strictly lowest validation BIC among train-MSE-selected starts and a predeclared >=10.0 BIC gap to second place.",
            "std_4r3c_validation_bic": std4["validation_bic"],
            "next_best_model": next_best["model"],
            "bic_gap_to_next": bic_gap,
        },
        "criterion_b": {
            "passed": criterion_b,
            "definition": "Oracle passes; all 19 labels use the identical logged start protocol; empirical sampled-start dispersion is recorded.",
            "oracle_passed": oracle["passed"],
            "uniform_protocol": uniform,
            "dispersion_documented": dispersion_documented,
        },
        "config": merged["config"],
        "selection_rule": "Minimum train MSE only; validation and test were never used to select a restart.",
        "residual_convention": "Tin_measured - Tin_estimated",
        "sensitivity_banner_required": verdict_kind == "B",
        "sensitivity_by_structure": sensitivity,
        "conclusion": (
            "VALIDATED_MULTISTART_ARTICLE_RANKING"
            if verdict_kind == "A"
            else "VALIDATED_INITIALIZATION_SENSITIVE"
            if verdict_kind == "B"
            else "FAILED_MULTISTART_PROTOCOL"
        ),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_cell(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _basin_markdown(summaries: Sequence[dict[str, object]]) -> str:
    lines = [
        "# Dispersion empirique des initialisations M4",
        "",
        "Ces plages décrivent seulement les résultats des départs échantillonnés ; ce ne sont pas des intervalles de confiance statistiques.",
        "",
        "| Structure | Départs finis / total | MSE train q05–q95 | BIC validation q05–q95 | Confiance d’identification |",
        "|---|---:|---:|---:|---|",
    ]
    for item in sorted(summaries, key=lambda row: int(row["model_index"])):
        train = f"{item['train_mse_q05']:.6g}–{item['train_mse_q95']:.6g}" if item["train_mse_q05"] is not None else "n/a"
        bic = f"{item['validation_bic_q05']:.3f}–{item['validation_bic_q95']:.3f}" if item["validation_bic_q05"] is not None else "n/a"
        lines.append(
            f"| {item['model']} | {item['n_finite_train_runs']} / {item['n_starts']} | {train} | {bic} | {item['identification_confidence']} |"
        )
    return "\n".join(lines) + "\n"


def write_multistart_artifacts(
    project_root: Path | str,
    merged: dict[str, object],
    oracle: dict[str, object],
    verdict: dict[str, object],
) -> dict[str, Path]:
    """Persist full attempts, protocol provenance, selected fits and dispersion."""

    root = Path(project_root).resolve()
    run_dir = root / "runs" / "m4"
    multi_dir = run_dir / "multistart"
    multi_dir.mkdir(parents=True, exist_ok=True)
    old_verdict = run_dir / "verdict.json"
    backup = run_dir / "single_start_verdict.json"
    if old_verdict.is_file() and not backup.is_file():
        shutil.copy2(old_verdict, backup)
    source_csv = root / "data" / "processed" / "hourly_reference.csv"
    protocol = {
        "protocol": "uniform_multistart_notebook_cell_55",
        "config": merged["config"],
        "random_start_distribution": "uniform in frozen log-space bounds (therefore log-uniform physical parameters)",
        "first_start": "notebook initial R=0.2, C=1e7, alpha=1e-4",
        "selection_rule": "minimum finite train MSE; deterministic start-id tie-break; success=False remains eligible when MSE is finite",
        "validation_test_usage": "evaluated and journaled, never used to select an in-topology restart",
        "topology_ranking": "validation BIC only among retained train-selected fits",
        "strong_bic_gap_for_route_a": STRONG_BIC_GAP,
        "near_best_train_definition": f"MSE <= MSE_min * (1 + {NEAR_BEST_TRAIN_FRACTION})",
        "source_csv": str(source_csv),
        "source_csv_sha256": _sha256(source_csv) if source_csv.is_file() else None,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
    }
    all_path = multi_dir / "all_starts.json"
    all_csv_path = multi_dir / "all_starts.csv"
    starts_path = multi_dir / "starts.csv"
    selected_path = multi_dir / "selected_by_train_mse.csv"
    basin_path = multi_dir / "basin_dispersion.csv"
    basin_md_path = multi_dir / "basin_dispersion.md"
    protocol_path = multi_dir / "protocol.json"
    oracle_path = multi_dir / "notebook_parameter_oracle.json"
    verdict_path = run_dir / "verdict.json"
    all_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outcome_rows = []
    for item in merged["outcomes"]:
        row = dict(item)
        row["initial_parameters_log"] = _json_cell(row["initial_parameters_log"])
        row["final_parameters_log"] = _json_cell(row["final_parameters_log"])
        outcome_rows.append(row)
    pd.DataFrame(outcome_rows).sort_values(["model_index", "start_id"]).to_csv(all_csv_path, index=False)
    pd.DataFrame(
        [
            {
                "model": item["model"],
                "model_index": item["model_index"],
                "start_id": item["start_id"],
                "start_kind": item["start_kind"],
                "start_seed": item["start_seed"],
                "initial_parameters_log": _json_cell(item["initial_parameters_log"]),
            }
            for item in merged["outcomes"]
        ]
    ).sort_values(["model_index", "start_id"]).to_csv(starts_path, index=False)
    pd.DataFrame(merged["selected"]).sort_values("validation_bic").to_csv(selected_path, index=False)
    pd.DataFrame(merged["basin_summaries"]).sort_values("model_index").to_csv(basin_path, index=False)
    basin_md_path.write_text(_basin_markdown(merged["basin_summaries"]), encoding="utf-8")
    protocol_path.write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    oracle_path.write_text(json.dumps(oracle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verdict_path.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "all_starts": all_path,
        "all_starts_csv": all_csv_path,
        "starts": starts_path,
        "selected": selected_path,
        "basin_dispersion": basin_path,
        "basin_markdown": basin_md_path,
        "protocol": protocol_path,
        "oracle": oracle_path,
        "verdict": verdict_path,
        "single_start_backup": backup,
    }
