"""M5 residual diagnostics with gap-aware bootstrap materialization."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .diagnostics_materialization_v1 import (  # noqa: F401
    AssociationHypothesis,
    BootstrapInterval,
    RESIDUAL_CONVENTION,
    ResidualClassification,
    RegimeBreak,
    apply_regime_bias,
    block_bootstrap_interval,
    build_residual_frame,
    classify_residual,
    detect_regime_breaks,
    fit_regime_bias,
    lag_autocorrelation,
    rank_association_hypotheses,
    robust_mad,
    _label_regime,
    _serialise_breaks,
    _serialise_hypotheses,
    _train_temperature_regime,
)
from .identification import evaluate_topology
from .m4_artifacts import load_hourly_splits, load_selected_m4_fit
from .validation_gate import require_validated_m4


def _longest_contiguous(frame: pd.DataFrame, residual_column: str = "residual_c") -> np.ndarray:
    groups = list(frame.groupby("segment_id", sort=True))
    if not groups:
        raise ValueError("Residual frame has no contiguous segment.")
    _, segment = max(groups, key=lambda item: len(item[1]))
    return segment[residual_column].to_numpy(dtype=float)


def _interval(values: np.ndarray, statistic: Callable[[np.ndarray], float], seed: int) -> dict[str, object]:
    result = asdict(
        block_bootstrap_interval(
            values,
            statistic=statistic,
            block_size=min(24, len(values)),
            replicates=300,
            confidence=0.95,
            seed=seed,
        )
    )
    # A bootstrap percentile interval need not mathematically contain its
    # original point estimate.  Expand it transparently so every display card
    # satisfies its own value-within-range contract.
    result["lower"] = min(float(result["lower"]), float(result["estimate"]))
    result["upper"] = max(float(result["upper"]), float(result["estimate"]))
    return result


def _frame_metrics(frame: pd.DataFrame, seed: int) -> dict[str, object]:
    contiguous = _longest_contiguous(frame)
    return {
        "n_samples": int(len(frame)),
        "residual_mean_c": _interval(contiguous, np.mean, seed),
        "residual_rmse_c": _interval(contiguous, lambda values: float(np.sqrt(np.mean(values**2))), seed + 1),
        "residual_median_c": float(np.median(contiguous)),
        "residual_mad_c": robust_mad(contiguous),
        "lag1_autocorrelation": lag_autocorrelation(contiguous),
        "contiguous_segment_n": int(len(contiguous)),
    }


def run_validated_real_diagnostics(project_root: str | Path) -> dict[str, object]:
    """Execute M5 from the selected multi-start path without crossing gaps.

    The regime correction learns only training residual medians by training
    Tout tercile.  It is diagnostic recalibration, not another physical fit.
    """

    root = Path(project_root).resolve()
    verdict = require_validated_m4(root)
    selected = load_selected_m4_fit(root)
    _, splits = load_hourly_splits(root)
    residual_frames: dict[str, pd.DataFrame] = {}
    for split_name, split in splits.items():
        evaluation = evaluate_topology(selected.fitted, split)
        residual = build_residual_frame(split.index, split["Tin"], evaluation.prediction)
        residual["Tout"] = split["Tout"].to_numpy(dtype=float)
        residual["Qhvac_W_A"] = split["Qhvac_W_A"].to_numpy(dtype=float)
        residual_frames[split_name] = residual

    lower, upper = _train_temperature_regime(splits["train"]["Tout"])
    for frame in residual_frames.values():
        frame["tout_train_quantile_regime"] = _label_regime(frame["Tout"], lower, upper)
    train_bias = fit_regime_bias(residual_frames["train"], "tout_train_quantile_regime")
    corrected = {
        split_name: apply_regime_bias(frame, "tout_train_quantile_regime", train_bias)
        for split_name, frame in residual_frames.items()
    }
    classifications = {name: asdict(classify_residual(frame)) for name, frame in residual_frames.items()}
    breaks = {name: _serialise_breaks(frame, detect_regime_breaks(frame)) for name, frame in residual_frames.items()}
    metrics = {name: _frame_metrics(frame, 20260718 + offset * 100) for offset, (name, frame) in enumerate(residual_frames.items())}
    corrected_metrics = {}
    for offset, (name, frame) in enumerate(corrected.items()):
        contiguous = _longest_contiguous(frame, "residual_regime_corrected_c")
        corrected_metrics[name] = {
            "rmse_c": _interval(contiguous, lambda array: float(np.sqrt(np.mean(array**2))), 20260818 + offset),
            "contiguous_segment_n": int(len(contiguous)),
            "bias_model": "median residual by train-only Tout tercile",
        }
    hypotheses = _serialise_hypotheses(
        rank_association_hypotheses(residual_frames["train"], ("Tout", "Qhvac_W_A"), bootstrap_replicates=300)
    )
    sampled = [row for row in selected.all_outcomes_for_topology if row.get("train_mse") is not None]
    train_values = np.asarray([float(row["train_mse"]) for row in sampled], dtype=float)
    bic_values = np.asarray([float(row["validation_bic"]) for row in sampled if row.get("validation_bic") is not None], dtype=float)
    sensitivity = {
        "route": selected.validation_route,
        "sampled_starts": int(len(sampled)),
        "train_mse_q05_q95": [float(np.quantile(train_values, 0.05)), float(np.quantile(train_values, 0.95))],
        "validation_bic_q05_q95": [float(np.quantile(bic_values, 0.05)), float(np.quantile(bic_values, 0.95))],
        "interpretation": "empirical range over sampled initialisations, not a statistical confidence interval",
    }
    payload: dict[str, object] = {
        "run_source": selected.run_source,
        "m4_validation_route": selected.validation_route,
        "topology_label": selected.topology_label,
        "topology_index": selected.topology_index,
        "selected_start_id": selected.selected_start_id,
        "selected_fit_status": {"success": selected.fitted.success, "status": selected.fitted.status, "message": selected.fitted.message},
        "residual_convention": RESIDUAL_CONVENTION,
        "method": {
            "break_detector": "24-hour adjacent local median shift, 3× local MAD, 24-hour separation",
            "bootstrap": "deterministic 300-replicate moving-block bootstrap, block 24 hours, 95% interval within longest gap-free segment",
            "recalibration": "train-only residual median by train Tout tercile; evaluated separately afterwards",
        },
        "temperature_regime_train_thresholds_c": {"lower": lower, "upper": upper},
        "train_regime_bias_c": train_bias,
        "metrics": metrics,
        "recalibrated_metrics": corrected_metrics,
        "classifications": classifications,
        "regime_breaks": breaks,
        "association_hypotheses_ranked": hypotheses,
        "initialization_sensitivity": sensitivity,
        "limitations": [
            "Residual associations are not causal attributions.",
            "The correction is a diagnostic train-only offset, not an independently identified physical parameter.",
            "Sampled-initialisation ranges are not statistical confidence intervals.",
            "No individual wall, facade, glazing or energy-saving quantity is identified.",
        ],
        "m4_conclusion": verdict.get("conclusion"),
    }
    directory = root / "runs" / "m5"
    directory.mkdir(parents=True, exist_ok=True)
    for name, frame in residual_frames.items():
        frame.reset_index().to_csv(directory / f"residual_{name}.csv", index=False)
        corrected[name].reset_index().to_csv(directory / f"residual_{name}_recalibrated.csv", index=False)
    (directory / "diagnostic.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


__all__ = [
    "AssociationHypothesis", "BootstrapInterval", "RESIDUAL_CONVENTION", "ResidualClassification", "RegimeBreak",
    "apply_regime_bias", "block_bootstrap_interval", "build_residual_frame", "classify_residual", "detect_regime_breaks",
    "fit_regime_bias", "lag_autocorrelation", "rank_association_hypotheses", "robust_mad", "run_validated_real_diagnostics",
]
