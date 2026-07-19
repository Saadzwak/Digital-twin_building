"""M5 residual diagnostics materialized only from a validated M4 run."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .diagnostics_base import (  # noqa: F401
    AssociationHypothesis,
    BootstrapInterval,
    RESIDUAL_CONVENTION,
    ResidualClassification,
    RegimeBreak,
    apply_regime_bias,
    block_bootstrap_interval,
    build_residual_frame,
    classify_residual,
    fit_regime_bias,
    lag_autocorrelation,
    rank_association_hypotheses,
    robust_mad,
)
from .m4_artifacts import load_hourly_splits, load_selected_m4_fit
from .identification import evaluate_topology
from .validation_gate import require_validated_m4


def detect_regime_breaks(
    residual_frame: pd.DataFrame,
    window: int = 24,
    threshold_mad: float = 3.0,
    minimum_separation: int = 24,
) -> list[RegimeBreak]:
    """Detect local robust-median shifts without crossing missing-data gaps."""

    if window < 3 or minimum_separation < 1:
        raise ValueError("window and minimum_separation must be positive practical integers.")
    breaks: list[RegimeBreak] = []
    for segment_id, segment in residual_frame.groupby("segment_id", sort=True):
        residual = segment["residual_c"].to_numpy(dtype=float)
        if len(residual) < 2 * window:
            continue
        last_position = -minimum_separation
        for position in range(window, len(residual) - window + 1):
            if position - last_position < minimum_separation:
                continue
            before_values = residual[position - window : position]
            after_values = residual[position : position + window]
            before = float(np.median(before_values))
            after = float(np.median(after_values))
            local_scale = max(1.4826 * robust_mad(before_values), 1.4826 * robust_mad(after_values), 0.05)
            shift = after - before
            if abs(shift) >= threshold_mad * local_scale:
                breaks.append(
                    RegimeBreak(
                        timestamp=pd.Timestamp(segment.index[position]),
                        segment_id=int(segment_id),
                        median_shift_c=shift,
                        robust_scale_c=local_scale,
                        evidence=f"adjacent {window}-sample local median shift exceeds {threshold_mad}×local MAD scale",
                    )
                )
                last_position = position
    return breaks


def _longest_contiguous(values: pd.DataFrame) -> np.ndarray:
    groups = list(values.groupby("segment_id", sort=True))
    if not groups:
        raise ValueError("Residual frame has no contiguous segment.")
    _, segment = max(groups, key=lambda item: len(item[1]))
    return segment["residual_c"].to_numpy(dtype=float)


def _interval(values: np.ndarray, statistic: Callable[[np.ndarray], float], seed: int) -> dict[str, object]:
    interval = block_bootstrap_interval(
        values,
        statistic=statistic,
        block_size=min(24, len(values)),
        replicates=300,
        confidence=0.95,
        seed=seed,
    )
    return asdict(interval)


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


def _train_temperature_regime(train_tout: pd.Series) -> tuple[float, float]:
    lower, upper = np.quantile(train_tout.to_numpy(dtype=float), [1 / 3, 2 / 3])
    return float(lower), float(upper)


def _label_regime(tout: pd.Series, lower: float, upper: float) -> pd.Series:
    return pd.Series(
        np.where(tout <= lower, "cold", np.where(tout <= upper, "mid", "warm")),
        index=tout.index,
        name="tout_train_quantile_regime",
    )


def _serialise_breaks(frame: pd.DataFrame, breaks: list[RegimeBreak]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in breaks:
        row = asdict(item)
        row["timestamp"] = item.timestamp.isoformat()
        # This robust local scale is explicitly a diagnostic scale, not an IC.
        row["uncertainty_note"] = "robust local MAD scale; not a statistical confidence interval"
        rows.append(row)
    return rows


def _serialise_hypotheses(items: list[AssociationHypothesis]) -> list[dict[str, object]]:
    return [
        {
            "covariate": item.covariate,
            "spearman_rho": item.spearman_rho,
            "interval": asdict(item.interval),
            "classification": item.classification,
            "wording": item.wording,
        }
        for item in items
    ]


def run_validated_real_diagnostics(project_root: str | Path) -> dict[str, object]:
    """Compute, execute and persist M5 evidence from the selected M4 trajectory.

    Recalibration is a diagnostic train-only residual offset by training Tout
    tercile.  It is neither a new identification fit nor a claim of a physical
    cause.  Validation/test are never used to estimate its thresholds or bias.
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
    for split_name, frame in residual_frames.items():
        frame["tout_train_quantile_regime"] = _label_regime(frame["Tout"], lower, upper)
    train_bias = fit_regime_bias(residual_frames["train"], "tout_train_quantile_regime")
    corrected = {
        split_name: apply_regime_bias(frame, "tout_train_quantile_regime", train_bias)
        for split_name, frame in residual_frames.items()
    }
    classifications = {split_name: asdict(classify_residual(frame)) for split_name, frame in residual_frames.items()}
    breaks = {
        split_name: _serialise_breaks(frame, detect_regime_breaks(frame))
        for split_name, frame in residual_frames.items()
    }
    metrics = {
        split_name: _frame_metrics(frame, 20260718 + offset * 100)
        for offset, (split_name, frame) in enumerate(residual_frames.items())
    }
    corrected_metrics = {}
    for offset, (split_name, frame) in enumerate(corrected.items()):
        values = frame["residual_regime_corrected_c"].to_numpy(dtype=float)
        corrected_metrics[split_name] = {
            "rmse_c": _interval(values, lambda array: float(np.sqrt(np.mean(array**2))), 20260818 + offset),
            "bias_model": "median residual by train-only Tout tercile",
        }
    hypotheses = _serialise_hypotheses(
        rank_association_hypotheses(residual_frames["train"], ("Tout", "Qhvac_W_A"), bootstrap_replicates=300)
    )
    sampled = [row for row in selected.all_outcomes_for_topology if row.get("train_mse") is not None]
    train_values = np.asarray([float(row["train_mse"]) for row in sampled], dtype=float)
    val_bic_values = np.asarray([float(row["validation_bic"]) for row in sampled if row.get("validation_bic") is not None], dtype=float)
    sensitivity = {
        "route": selected.validation_route,
        "sampled_starts": int(len(sampled)),
        "train_mse_q05_q95": [float(np.quantile(train_values, 0.05)), float(np.quantile(train_values, 0.95))],
        "validation_bic_q05_q95": [float(np.quantile(val_bic_values, 0.05)), float(np.quantile(val_bic_values, 0.95))],
        "interpretation": "empirical range over sampled initialisations, not a statistical confidence interval",
    }
    payload: dict[str, object] = {
        "run_source": selected.run_source,
        "m4_validation_route": selected.validation_route,
        "topology_label": selected.topology_label,
        "topology_index": selected.topology_index,
        "selected_start_id": selected.selected_start_id,
        "selected_fit_status": {
            "success": selected.fitted.success,
            "status": selected.fitted.status,
            "message": selected.fitted.message,
        },
        "residual_convention": RESIDUAL_CONVENTION,
        "method": {
            "break_detector": "24-hour adjacent local median shift, 3× local MAD, 24-hour separation",
            "bootstrap": "deterministic 300-replicate moving-block bootstrap, block 24 hours, 95% interval",
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
    run_dir = root / "runs" / "m5"
    run_dir.mkdir(parents=True, exist_ok=True)
    for split_name, frame in residual_frames.items():
        frame.reset_index().to_csv(run_dir / f"residual_{split_name}.csv", index=False)
        corrected[split_name].reset_index().to_csv(run_dir / f"residual_{split_name}_recalibrated.csv", index=False)
    path = run_dir / "diagnostic.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


__all__ = [
    "AssociationHypothesis", "BootstrapInterval", "RESIDUAL_CONVENTION", "ResidualClassification",
    "RegimeBreak", "apply_regime_bias", "block_bootstrap_interval", "build_residual_frame",
    "classify_residual", "detect_regime_breaks", "fit_regime_bias", "lag_autocorrelation",
    "rank_association_hypotheses", "robust_mad", "run_validated_real_diagnostics",
]
