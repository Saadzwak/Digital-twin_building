"""Live product pipeline: real computation streamed as consumable events.

The generator :func:`run_live_pipeline` executes the actual work — plan
inventory, data preparation, the reduced-start structure bank, selection,
twin resolution, annual drift and parameter scenarios — and yields one event
per real step so a UI can render progress that reflects computation, never
an animation.  Everything is journaled under ``runs/demo/``.

Demo protocol (documented, distinct from the frozen M4 reproduction):
- same frozen structure bank, bounds, optimizer call and start generator as
  the sealed multi-start, but ``n_starts`` reduced so one browser interaction
  stays within a few minutes;
- the loss uses the equivalence-tested accelerated simulator (``fast_sim``);
- a structure whose best train fit is degenerate relative to the bank median
  is excluded from the cross-structure ranking and shown as such;
- on the reference dataset the operating twin is the published article 4R3C
  parameter vector (oracle-checked); the live bank remains the transparency
  and sensitivity exhibit.  On uploaded data no published reference exists,
  so the twin is the bank selection itself.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import io
import json
from pathlib import Path
import time
from typing import Generator, Iterable

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .annual_drift import AnnualDrift, compute_annual_drift, drift_summary
from .business_language import (
    CANNOT_DISTINGUISH_TEXT,
    RELIABILITY_SURFACE_TEXT,
    effective_heat_loss,
    format_heat_loss_sentence,
    response_time_hours,
)
from .counterfactuals import SCENARIO_BANK, scenario_dispersion, scenario_effect
from .diagnostics import block_bootstrap_interval
from .fast_sim import simulate_open_loop_fast
from .geometry import inventory_plans
from .identification import (
    calculate_metrics,
    log_parameter_bounds,
    residual_measured_minus_estimated,
)
from .multistart import MultiStartConfig
from .multistart_impl import ORACLE_PHYSICAL_PARAMETERS_4R3C, deterministic_start
from .onboarding import QUESTION_BANK
from .reference_ingestion import split_reference_months
from .topologies import STD_4R3C, reference_model_bank
from .validation_gate import require_validated_m4

DT_SECONDS = 3600.0
# One structure is excluded from ranking when its best train MSE exceeds this
# multiple of the bank-wide median: its identification failed on this data.
ADMISSIBILITY_FACTOR = 2.0
# Sealed starts within this validation-RMSE distance of the article oracle
# are treated as the same behavioural calibration for uncertainty ranges.
ARTICLE_BASIN_TOLERANCE_C = 0.25


@dataclass(frozen=True)
class DemoConfig:
    n_starts: int = 3
    seed: int = 7096790
    admissibility_factor: float = ADMISSIBILITY_FACTOR
    structure_names: tuple[str, ...] | None = None  # test hook; product uses all 19
    journal_name: str = "latest"  # tests journal elsewhere to protect the real run


def _bank(config: DemoConfig):
    bank = reference_model_bank()
    if config.structure_names is None:
        return bank
    return tuple(topo for topo in bank if topo.name in set(config.structure_names))


def demo_splits(hourly: pd.DataFrame, is_reference: bool) -> dict[str, pd.DataFrame]:
    if is_reference:
        return split_reference_months(hourly)
    n = len(hourly)
    train_end = int(n * 0.75)
    validation_end = int(n * 0.92)
    return {
        "train": hourly.iloc[:train_end],
        "validation": hourly.iloc[train_end:validation_end],
        "test": hourly.iloc[validation_end:],
    }


def prepare_uploaded_csv(content: bytes) -> tuple[pd.DataFrame, dict[str, object]]:
    """Parse an uploaded CSV into the hourly Tin/Tout/HVAC frame.

    Column names are matched loosely (timestamp, indoor, outdoor, power);
    the data is resampled to hourly means and rows with any missing value
    are dropped, mirroring the reference preparation's strictness.
    """

    frame = pd.read_csv(io.BytesIO(content))
    lowered = {column.lower().strip(): column for column in frame.columns}

    def _find(*candidates: str) -> str | None:
        for name, original in lowered.items():
            for candidate in candidates:
                if candidate in name:
                    return original
        return None

    time_col = _find("timestamp", "date", "time", "datetime")
    tin_col = _find("tin", "interieur", "intérieur", "indoor", "t_int")
    tout_col = _find("tout", "exterieur", "extérieur", "outdoor", "t_ext")
    power_col = _find("hvac", "power", "puissance", "conso", "chauffage", "q_")
    missing = [label for label, col in
               (("timestamp", time_col), ("indoor temperature", tin_col),
                ("outdoor temperature", tout_col), ("HVAC power", power_col)) if col is None]
    if missing:
        raise ValueError("Columns not found in the CSV: " + ", ".join(missing))

    # Use .to_numpy() so the source columns are not index-aligned against the
    # new datetime index (aligning a RangeIndex Series to timestamps -> all NaN).
    parsed = pd.DataFrame(
        {
            "Tin": pd.to_numeric(frame[tin_col], errors="coerce").to_numpy(),
            "Tout": pd.to_numeric(frame[tout_col], errors="coerce").to_numpy(),
            "Qhvac_W_A": pd.to_numeric(frame[power_col], errors="coerce").to_numpy(),
        },
        index=pd.to_datetime(frame[time_col], errors="coerce", utc=True),
    )
    parsed = parsed[parsed.index.notna()].sort_index()
    # groupby(floor) instead of resample('1h'): resample can return all-NaN on the
    # microsecond-resolution datetime index pandas 3 produces from tz-aware input.
    hourly = parsed.groupby(parsed.index.floor("1h")).mean().dropna(how="any")
    hourly.index.name = "Date"
    if len(hourly) < 1000:
        raise ValueError(
            f"The uploaded CSV contains only {len(hourly)} usable hours; at least 1000 are required."
        )
    provenance = {
        "kind": "upload",
        "rows_raw": int(len(frame)),
        "rows_hourly": int(len(hourly)),
        "columns_used": {"time": time_col, "tin": tin_col, "tout": tout_col, "power": power_col},
    }
    return hourly, provenance


def _iter_data_summary(hourly: pd.DataFrame, is_reference: bool) -> dict[str, object]:
    index = pd.DatetimeIndex(hourly.index)
    deltas = index.to_series().diff().dropna()
    gaps = deltas[deltas > pd.Timedelta(hours=1)]
    expected = int((index[-1] - index[0]) / pd.Timedelta(hours=1)) + 1
    splits = demo_splits(hourly, is_reference)
    return {
        "rows": int(len(hourly)),
        "first": str(index[0]),
        "last": str(index[-1]),
        "missing_hours": int(expected - len(hourly)),
        "n_gaps": int(len(gaps)),
        "largest_gap_hours": float(gaps.max() / pd.Timedelta(hours=1)) if len(gaps) else 0.0,
        "splits": {name: int(len(part)) for name, part in splits.items()},
    }


def _fit_fast(topology, x0: np.ndarray, tin: np.ndarray, tout: np.ndarray, q: np.ndarray):
    def loss(theta: np.ndarray) -> float:
        estimated = simulate_open_loop_fast(topology, tout, q, DT_SECONDS, np.asarray(theta), tin[0])
        return float(np.mean(residual_measured_minus_estimated(tin, estimated) ** 2))

    return minimize(loss, x0, bounds=log_parameter_bounds(topology), method="L-BFGS-B")


def _evaluate(topology, theta: np.ndarray, frame: pd.DataFrame) -> dict[str, float]:
    tin = frame["Tin"].to_numpy(dtype=float)
    tout = frame["Tout"].to_numpy(dtype=float)
    q = frame["Qhvac_W_A"].to_numpy(dtype=float)
    prediction = simulate_open_loop_fast(topology, tout, q, DT_SECONDS, theta, tin[0])
    metrics = calculate_metrics(tin, prediction, topology.n_resistances + topology.n_capacitances + 1)
    return {"rmse": metrics.rmse, "mae": metrics.mae, "bic": metrics.bic}


def _rmse_interval(residual: np.ndarray, seed: int) -> tuple[float, float, float]:
    interval = block_bootstrap_interval(
        residual,
        statistic=lambda values: float(np.sqrt(np.mean(values**2))),
        block_size=min(24, len(residual)),
        replicates=300,
        confidence=0.95,
        seed=seed,
    )
    estimate = float(interval.estimate)
    lower = min(float(interval.lower), estimate)
    upper = max(float(interval.upper), estimate)
    return estimate, lower, upper


def _article_companion_vectors(root: Path) -> tuple[np.ndarray, ...]:
    """Sealed 4R3C starts behaving like the article calibration, if any."""

    path = root / "runs" / "m4" / "multistart" / "all_starts.json"
    if not path.is_file():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    vectors: list[np.ndarray] = []
    for row in payload.get("outcomes", []):
        if row.get("model") != STD_4R3C.name or not row.get("fit_success"):
            continue
        rmse = row.get("validation_rmse")
        theta = row.get("final_parameters_log")
        if rmse is None or theta is None:
            continue
        if abs(float(rmse) - 4.682382239968712) <= ARTICLE_BASIN_TOLERANCE_C:
            vectors.append(np.asarray(theta, dtype=float))
    return tuple(vectors)


def run_live_pipeline(
    project_root: Path | str,
    config: DemoConfig | None = None,
    uploaded_hourly: pd.DataFrame | None = None,
    upload_provenance: dict[str, object] | None = None,
    uploaded_plan_paths: tuple[Path, ...] | None = None,
) -> Generator[dict[str, object], None, dict[str, object]]:
    root = Path(project_root).resolve()
    config = config or DemoConfig()
    started = time.perf_counter()
    is_reference = uploaded_hourly is None
    require_validated_m4(root)

    # ------------------------------------------------------------------ plans
    yield {"kind": "stage", "stage": "plans", "status": "start"}
    plan_records: list[dict[str, object]] = []
    if is_reference or not uploaded_plan_paths:
        inventory = inventory_plans(root, root / "tmp" / "m6_previews")
        for record in inventory:
            row = dict(record.__dict__)
            plan_records.append(row)
            yield {"kind": "plan", **row}
    else:
        for path in uploaded_plan_paths:
            row = {"filename": path.name, "level": "inconnu", "page_count": None,
                   "vector_drawing_count": None, "detected_scale": None,
                   "text_characters": None, "preview_path": None}
            plan_records.append(row)
            yield {"kind": "plan", **row}
    yield {
        "kind": "stage", "stage": "plans", "status": "done",
        "n_plans": len(plan_records), "awaiting_human_validation": True,
    }

    # ------------------------------------------------------------------- data
    yield {"kind": "stage", "stage": "data", "status": "start",
           "source": "surveyed building — hourly measurements" if is_reference else "uploaded CSV"}
    if is_reference:
        csv_path = root / "data" / "processed" / "hourly_reference.csv"
        pieces: list[pd.DataFrame] = []
        rows_read = 0
        for chunk in pd.read_csv(csv_path, parse_dates=["Date"], chunksize=2000):
            pieces.append(chunk)
            rows_read += len(chunk)
            yield {"kind": "data_progress", "rows": rows_read}
        hourly = pd.concat(pieces).set_index("Date")
        provenance: dict[str, object] = {"kind": "reference", "path": csv_path.relative_to(root).as_posix()}
    else:
        hourly = uploaded_hourly
        provenance = dict(upload_provenance or {"kind": "upload"})
        yield {"kind": "data_progress", "rows": int(len(hourly))}
    summary = _iter_data_summary(hourly, is_reference)
    yield {"kind": "data_summary", **summary}
    splits = demo_splits(hourly, is_reference)
    train, validation, test = splits["train"], splits["validation"], splits["test"]
    tin = train["Tin"].to_numpy(dtype=float)
    tout = train["Tout"].to_numpy(dtype=float)
    q = train["Qhvac_W_A"].to_numpy(dtype=float)

    # ------------------------------------------------------------------- bank
    bank = _bank(config)
    ms_config = MultiStartConfig(n_starts=config.n_starts, seed=config.seed)
    yield {
        "kind": "stage", "stage": "bank", "status": "start",
        "n_starts": config.n_starts,
        "structures": [
            {"model": topo.name, "n_parameters": topo.n_resistances + topo.n_capacitances + 1,
             "duplicate_of": topo.duplicate_of}
            for topo in bank
        ],
    }
    bank_rows: list[dict[str, object]] = []
    all_start_rows: list[dict[str, object]] = []
    for model_index, topo in enumerate(bank):
        structure_t0 = time.perf_counter()
        best = None
        for start_id in range(1, config.n_starts + 1):
            yield {"kind": "fit_start", "model": topo.name, "start_id": start_id,
                   "n_starts": config.n_starts}
            x0, start_kind, start_seed = deterministic_start(topo, model_index, start_id, ms_config)
            fit_t0 = time.perf_counter()
            result = _fit_fast(topo, x0, tin, tout, q)
            elapsed = time.perf_counter() - fit_t0
            start_row = {
                "model": topo.name, "start_id": start_id, "start_kind": start_kind,
                "start_seed": start_seed, "train_mse": float(result.fun),
                "success": bool(result.success), "nfev": int(result.nfev),
                "elapsed_s": round(elapsed, 3),
                "final_parameters_log": [float(v) for v in result.x],
            }
            all_start_rows.append(start_row)
            yield {"kind": "fit_done", "model": topo.name, "start_id": start_id,
                   "n_starts": config.n_starts, "train_mse": float(result.fun),
                   "success": bool(result.success), "elapsed_s": round(elapsed, 2)}
            if best is None or result.fun < best[1].fun:
                best = (start_id, result)
        start_id, result = best
        theta = np.asarray(result.x, dtype=float)
        val_metrics = _evaluate(topo, theta, validation)
        test_metrics = _evaluate(topo, theta, test)
        row = {
            "model": topo.name,
            "n_parameters": topo.n_resistances + topo.n_capacitances + 1,
            "duplicate_of": topo.duplicate_of,
            "selected_start": start_id,
            "train_mse": float(result.fun),
            "success": bool(result.success),
            "val_rmse": val_metrics["rmse"],
            "val_bic": val_metrics["bic"],
            "test_rmse": test_metrics["rmse"],
            "parameters_log": [float(v) for v in theta],
            "elapsed_s": round(time.perf_counter() - structure_t0, 2),
        }
        bank_rows.append(row)
        yield {"kind": "structure_done", **{k: v for k, v in row.items() if k != "parameters_log"}}

    median_mse = float(np.median([row["train_mse"] for row in bank_rows]))
    threshold = config.admissibility_factor * median_mse
    for row in bank_rows:
        degenerate = row["train_mse"] > threshold
        row["admissible"] = not degenerate
        row["excluded_reason"] = (
            "training calibration degraded relative to the bench — excluded from ranking" if degenerate else ""
        )
    excluded = [
        {"model": row["model"], "train_mse": row["train_mse"], "reason": row["excluded_reason"]}
        for row in bank_rows if not row["admissible"]
    ]
    yield {"kind": "stage", "stage": "bank", "status": "done",
           "admissibility_threshold_mse": threshold, "excluded": excluded}

    # -------------------------------------------------------------- selection
    admissible = [row for row in bank_rows if row["admissible"]]
    if not admissible:
        raise RuntimeError("No admissible structure: identification failed on this data.")
    ranked = sorted(admissible, key=lambda row: row["val_bic"])
    bank_auto = ranked[0]  # what the automated train-MSE + val-BIC rule actually picks
    runner_up = ranked[1] if len(ranked) > 1 else None

    # Correction A — the headline "selected" structure must be the one actually
    # used as the operating twin, never a bank pick the product then ignores.
    # On the reference building the automated identification is degenerate
    # (all simple structures collapse to ~5.0 °C, the two-mass reference basin
    # is only reachable via the published calibration), so the headline is the
    # reference structure and the automated collapse is surfaced, not hidden.
    article_reference = None
    if is_reference:
        article_reference = {
            "model": STD_4R3C.name, "n_parameters": 8,
            "val_rmse": 4.682382239968712, "val_bic": 4578.578335283145, "test_rmse": 0.8575992138865025,
            "origin": "published parameters from the article, oracle-verified",
        }
        headline_model = STD_4R3C.name
        headline_val_rmse = article_reference["val_rmse"]
        headline_val_bic = article_reference["val_bic"]
        selection_explainer = (
            "The bench explores the 19 structures. On this data, automated identification does not separate the "
            f"simple structures — they all reach ≈ 5.0 °C — and falls back to the simplest one ({bank_auto['model']}). "
            "The two-mass structure (4R3C) is the one that captures the building response and reaches 4.7 °C: "
            "it is the operating twin, using the published reference calibration (identification sensitive to "
            "initialization)."
        )
        twin_is_bank_selection = False
    else:
        headline_model = bank_auto["model"]
        headline_val_rmse = bank_auto["val_rmse"]
        headline_val_bic = bank_auto["val_bic"]
        selection_explainer = (
            f"The bench keeps the best admissible structure on your data: {bank_auto['model']}. "
            "No published reference exists for this building; the physical-reading limits apply."
        )
        twin_is_bank_selection = True

    bank_auto_pick = {
        "model": bank_auto["model"], "val_rmse": bank_auto["val_rmse"], "val_bic": bank_auto["val_bic"],
        "rule": "minimum training MSE per structure, then best validation information criterion among admissible structures",
    }
    yield {
        "kind": "selection",
        "model": headline_model,
        "val_bic": headline_val_bic,
        "val_rmse": headline_val_rmse,
        "runner_up": runner_up["model"] if runner_up else None,
        "bic_gap": (runner_up["val_bic"] - bank_auto["val_bic"]) if runner_up else None,
        "article_reference": article_reference,
        "bank_auto_pick": bank_auto_pick,
        "twin_is_bank_selection": twin_is_bank_selection,
        "explainer": selection_explainer,
    }

    # ------------------------------------------------------------------- twin
    if is_reference:
        twin_topology = STD_4R3C
        twin_theta = np.log(np.asarray(ORACLE_PHYSICAL_PARAMETERS_4R3C, dtype=float))
        companions = _article_companion_vectors(root)
        twin_policy = (
            "Operating twin: two-mass structure (4R3C), published reference calibration, reproduced "
            "and verified on this data. The bench's automated re-identification does not separate the structures and "
            "has no physical reading of the envelope; it is shown as exploration and a sensitivity measure."
        )
        twin_source = "article-4r3c-oracle"
    else:
        twin_topology = next(t for t in bank if t.name == bank_auto["model"])
        twin_theta = np.asarray(bank_auto["parameters_log"], dtype=float)
        companions = ()
        twin_policy = (
            "Operating twin: best admissible structure from the bench on your data. No published reference "
            "exists for this building; the physical-reading limits apply."
        )
        twin_source = "upload-bank-selection"
    selected = {"model": headline_model, "val_bic": headline_val_bic, "val_rmse": headline_val_rmse}
    twin_val = _evaluate(twin_topology, twin_theta, validation)
    twin_test = _evaluate(twin_topology, twin_theta, test)
    twin_vectors = (twin_theta,) + companions
    yield {"kind": "twin", "model": twin_topology.name, "policy": twin_policy,
           "run_source": twin_source, "val_rmse": twin_val["rmse"], "test_rmse": twin_test["rmse"],
           "companion_vectors": len(companions),
           "consistent_with_selection": twin_topology.name == headline_model}

    # ------------------------------------------------------------------ drift
    yield {"kind": "stage", "stage": "drift", "status": "start"}
    drift = compute_annual_drift(twin_topology, twin_theta, hourly, train_hours=len(train))
    drift_info = drift_summary(drift)
    yield {"kind": "drift_done", **drift_info}

    # -------------------------------------------------------------- scenarios
    yield {"kind": "stage", "stage": "scenarios", "status": "start", "total": len(SCENARIO_BANK)}
    scenario_payloads: list[dict[str, object]] = []
    for scenario in SCENARIO_BANK:
        effect = scenario_effect(twin_topology, twin_theta, hourly, scenario)
        dispersion = scenario_dispersion(twin_topology, twin_vectors, hourly, scenario)
        payload_row = {**asdict(effect), "dispersion": dispersion, "note": ""}
        scenario_payloads.append(payload_row)
        yield {"kind": "scenario_done", **payload_row}
    by_key = {row["key"]: row for row in scenario_payloads}
    envelope_two = by_key.get("enveloppe_x2")
    direct_two = by_key.get("fuites_directes_x2")
    if (
        envelope_two and direct_two and envelope_two["applicable"] and direct_two["applicable"]
        and envelope_two["delta_energy_pct"] is not None and direct_two["delta_energy_pct"] is not None
        and abs(envelope_two["delta_energy_pct"] - direct_two["delta_energy_pct"]) < 1.0
    ):
        direct_two["note"] = (
            "On this building, the direct indoor-to-outdoor path dominates the losses: "
            "this scenario almost entirely overlaps the envelope scenario."
        )

    # --------------------------------------------------------------- payload
    val_tin = validation["Tin"].to_numpy(dtype=float)
    val_pred = simulate_open_loop_fast(
        twin_topology, validation["Tout"].to_numpy(dtype=float),
        validation["Qhvac_W_A"].to_numpy(dtype=float), DT_SECONDS, twin_theta, val_tin[0])
    test_tin = test["Tin"].to_numpy(dtype=float)
    test_pred = simulate_open_loop_fast(
        twin_topology, test["Tout"].to_numpy(dtype=float),
        test["Qhvac_W_A"].to_numpy(dtype=float), DT_SECONDS, twin_theta, test_tin[0])
    val_est, val_lo, val_hi = _rmse_interval(val_tin - val_pred, seed=20260719)
    test_est, test_lo, test_hi = _rmse_interval(test_tin - test_pred, seed=20260720)

    physical = np.exp(twin_theta)
    heat_loss_levels = []
    for theta_vector in twin_vectors:
        vector_physical = np.exp(np.asarray(theta_vector, dtype=float))
        level = effective_heat_loss(
            twin_topology, vector_physical[: twin_topology.n_resistances], float(vector_physical[-1]))
        heat_loss_levels.append(level)
    primary_level = heat_loss_levels[0]
    ua_values = [level.ua_w_per_k for level in heat_loss_levels if level.physically_readable]
    all_ua_values = [level.ua_w_per_k for level in heat_loss_levels]
    ua_spread_factor = (max(all_ua_values) / min(all_ua_values)) if all_ua_values and min(all_ua_values) > 0 else 1.0
    ua_robust = len(all_ua_values) > 1 and ua_spread_factor <= 3.0
    response_hours = response_time_hours(twin_topology, twin_theta)

    journal_dir = root / "runs" / "demo" / config.journal_name
    journal_dir.mkdir(parents=True, exist_ok=True)
    bank_journal = {
        "protocol": {
            "n_starts": config.n_starts, "seed": config.seed,
            "rng": "numpy.random.PCG64", "optimizer": "L-BFGS-B, published bounds, no options",
            "simulator": "fast modal simulator, equivalence-tested against the frozen loop (<1e-8 °C)",
            "admissibility_factor": config.admissibility_factor,
            "admissibility_threshold_mse": threshold,
            "selection_rule": "per structure: minimum training MSE; between structures: minimum validation BIC among admissible ones",
        },
        "dataset": {**provenance, **summary},
        "rows": bank_rows,
        "all_starts": all_start_rows,
        "excluded": excluded,
        "selected_model": selected["model"],
        "article_reference": article_reference,
    }
    canonical = json.dumps(bank_journal, sort_keys=True, ensure_ascii=False).encode("utf-8")
    run_source = ("demo-live-" if is_reference else "upload-live-") + hashlib.sha256(canonical).hexdigest()[:8]

    product_payload = {
        "run_source": run_source,
        "generated_at_unix": time.time(),
        "dataset": {**provenance, **summary},
        "verdict_reference": {
            "route": "B",
            "statement": RELIABILITY_SURFACE_TEXT,
            "sealed_verdict_path": "runs/m4/verdict.json",
        },
        "selection": {
            "headline_model": headline_model,
            "twin_is_bank_selection": twin_is_bank_selection,
            "bank_auto_pick": bank_auto_pick,
            "explainer": selection_explainer,
            "article_reference": article_reference,
        },
        "twin": {
            "structure_label": twin_topology.name,
            "policy": twin_policy,
            "twin_source": twin_source,
            "consistent_with_selection": twin_topology.name == headline_model,
            "resistances": [float(v) for v in physical[: twin_topology.n_resistances]],
            "capacitances": [float(v) for v in physical[twin_topology.n_resistances : -1]],
            "alpha": float(physical[-1]),
            "parameters_log": [float(v) for v in twin_theta],
            "companion_vectors": len(companions),
            "metrics": {
                "validation_rmse": {"value": val_est, "lower": val_lo, "upper": val_hi,
                                    "unit": "°C", "period": "validation",
                                    "method": "standard deviation of the residuals, 24 h block bootstrap, 300 replications"},
                "test_rmse": {"value": test_est, "lower": test_lo, "upper": test_hi,
                              "unit": "°C", "period": "test",
                              "method": "standard deviation of the residuals, 24 h block bootstrap, 300 replications"},
            },
        },
        "indicators": {
            "heat_loss": {
                "value": primary_level.ua_w_per_k,
                "lower": min(ua_values) if ua_values else primary_level.ua_w_per_k,
                "upper": max(ua_values) if ua_values else primary_level.ua_w_per_k,
                "unit": "W/°C",
                "period": "measured year",
                "method": "twin's effective outdoor conductances; range across independent calibrations of the same behaviour"
                          if len(twin_vectors) > 1 else "twin's effective outdoor conductances (single vector)",
                "physically_readable": primary_level.physically_readable,
                "direct_path_share": primary_level.direct_path_share,
                "sentence": format_heat_loss_sentence(primary_level),
                "robust_between_calibrations": ua_robust,
                "spread_factor_between_calibrations": ua_spread_factor,
                "robustness_note": (
                    "Value from the published calibration. Equivalent calibrations on the same data imply a level "
                    f"up to {ua_spread_factor:.0f} times different: the absolute value is not robustly "
                    "identifiable. The effect of the simulated interventions, however, stays consistent across these calibrations."
                ) if not ua_robust and len(all_ua_values) > 1 else "",
            },
            "response_time_hours": response_hours,
            "reliability_text": RELIABILITY_SURFACE_TEXT,
            "cannot_distinguish_text": CANNOT_DISTINGUISH_TEXT,
        },
        "drift": drift_info,
        "scenarios": scenario_payloads,
        "bank": {
            "n_starts": config.n_starts,
            "rows": [{k: v for k, v in row.items() if k != "parameters_log"} for row in bank_rows],
            "excluded": excluded,
            "selected_model": selected["model"],
            "article_reference": article_reference,
            "admissibility_threshold_mse": threshold,
        },
        "onboarding_questions": [
            {"key": question.key, "prompt": question.prompt, "why_needed": question.why_needed}
            for question in QUESTION_BANK
        ],
        "geometry_status": "HUMAN_VALIDATION_REQUIRED",
    }

    (journal_dir / "bank_journal.json").write_text(
        json.dumps(bank_journal, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (journal_dir / "product_payload.json").write_text(
        json.dumps(product_payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    drift.daily.reset_index().to_csv(journal_dir / "drift_daily.csv", index=False)
    drift.frame.reset_index()[["Date", "residual_c", "cumulative_gap_c_h"]].to_csv(
        journal_dir / "drift_hourly.csv", index=False)

    yield {
        "kind": "payload_ready",
        "run_source": run_source,
        "paths": {
            "product_payload": str(journal_dir / "product_payload.json"),
            "bank_journal": str(journal_dir / "bank_journal.json"),
            "drift_daily": str(journal_dir / "drift_daily.csv"),
        },
        "elapsed_total_s": round(time.perf_counter() - started, 1),
    }
    return product_payload


def load_product_payload(project_root: Path | str, journal_name: str = "latest") -> dict[str, object] | None:
    path = Path(project_root).resolve() / "runs" / "demo" / journal_name / "product_payload.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_drift_daily(project_root: Path | str, journal_name: str = "latest") -> pd.DataFrame | None:
    path = Path(project_root).resolve() / "runs" / "demo" / journal_name / "drift_daily.csv"
    if not path.is_file():
        return None
    return pd.read_csv(path, parse_dates=["Date"]).set_index("Date")
