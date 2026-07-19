"""Residual diagnostics that preserve sign, gaps, uncertainty and causal limits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .identification import residual_measured_minus_estimated
from .validation_gate import require_validated_m4


RESIDUAL_CONVENTION = "Tin_measured - Tin_estimated"


@dataclass(frozen=True)
class BootstrapInterval:
    estimate: float
    lower: float
    upper: float
    confidence: float
    replicates: int
    block_size: int


@dataclass(frozen=True)
class RegimeBreak:
    timestamp: pd.Timestamp
    segment_id: int
    median_shift_c: float
    robust_scale_c: float
    evidence: str


@dataclass(frozen=True)
class ResidualClassification:
    label: str
    signed_median_c: float
    mad_c: float
    lag1_autocorrelation: float | None
    rationale: str


@dataclass(frozen=True)
class AssociationHypothesis:
    covariate: str
    spearman_rho: float
    interval: BootstrapInterval
    classification: str
    wording: str


def build_residual_frame(
    index: Iterable[pd.Timestamp] | pd.DatetimeIndex,
    tin_measured: Iterable[float],
    tin_estimated: Iterable[float],
    expected_interval: pd.Timedelta = pd.Timedelta(hours=1),
    sensor_count: Iterable[float] | None = None,
    sensor_std_c: Iterable[float] | None = None,
) -> pd.DataFrame:
    """Create a gap-aware hourly residual table using measured minus estimated."""

    timestamps = pd.DatetimeIndex(index)
    measured = np.asarray(tuple(tin_measured), dtype=float)
    estimated = np.asarray(tuple(tin_estimated), dtype=float)
    if len(timestamps) != len(measured) or len(measured) != len(estimated):
        raise ValueError("index, measured and estimated must have the same length.")
    if len(timestamps) == 0 or not timestamps.is_monotonic_increasing or timestamps.has_duplicates:
        raise ValueError("index must be non-empty, strictly monotonic and unique.")
    if expected_interval <= pd.Timedelta(0):
        raise ValueError("expected_interval must be positive.")
    residual = residual_measured_minus_estimated(measured, estimated)
    gaps = timestamps.to_series().diff().gt(expected_interval * 1.5).fillna(False).to_numpy()
    segment_id = np.cumsum(gaps).astype(int)
    frame = pd.DataFrame(
        {
            "Tin_measured": measured,
            "Tin_estimated": estimated,
            "residual_c": residual,
            "segment_id": segment_id,
            "gap_before": gaps,
        },
        index=timestamps,
    )
    frame.index.name = "Date"
    if sensor_count is not None:
        values = np.asarray(tuple(sensor_count), dtype=float)
        if values.shape != measured.shape:
            raise ValueError("sensor_count must have the same length as measured.")
        frame["Tin_sensor_count"] = values
    if sensor_std_c is not None:
        values = np.asarray(tuple(sensor_std_c), dtype=float)
        if values.shape != measured.shape:
            raise ValueError("sensor_std_c must have the same length as measured.")
        frame["Tin_sensor_std_c"] = values
    return frame


def robust_mad(values: Iterable[float]) -> float:
    data = np.asarray(tuple(values), dtype=float)
    data = data[np.isfinite(data)]
    if len(data) == 0:
        return float("nan")
    median = np.median(data)
    return float(np.median(np.abs(data - median)))


def lag_autocorrelation(values: Iterable[float], lag: int = 1) -> float | None:
    data = np.asarray(tuple(values), dtype=float)
    if lag <= 0 or len(data) <= lag:
        return None
    left, right = data[:-lag], data[lag:]
    if np.std(left) == 0.0 or np.std(right) == 0.0:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def detect_regime_breaks(
    residual_frame: pd.DataFrame,
    window: int = 24,
    threshold_mad: float = 3.0,
    minimum_separation: int = 24,
) -> list[RegimeBreak]:
    """Detect dated median shifts without crossing missing-data gaps.

    It is a diagnostic detector, not a causal attribution or a fit adjustment.
    """

    if window < 3 or minimum_separation < 1:
        raise ValueError("window and minimum_separation must be positive practical integers.")
    breaks: list[RegimeBreak] = []
    for segment_id, segment in residual_frame.groupby("segment_id", sort=True):
        residual = segment["residual_c"].to_numpy(dtype=float)
        if len(residual) < 2 * window:
            continue
        scale = max(1.4826 * robust_mad(residual), 1e-9)
        last_position = -minimum_separation
        for position in range(window, len(residual) - window + 1):
            if position - last_position < minimum_separation:
                continue
            before = float(np.median(residual[position - window : position]))
            after = float(np.median(residual[position : position + window]))
            shift = after - before
            if abs(shift) >= threshold_mad * scale:
                breaks.append(
                    RegimeBreak(
                        timestamp=pd.Timestamp(segment.index[position]),
                        segment_id=int(segment_id),
                        median_shift_c=shift,
                        robust_scale_c=scale,
                        evidence=f"adjacent {window}-sample median shift exceeds {threshold_mad}×MAD scale",
                    )
                )
                last_position = position
    return breaks


def classify_residual(residual_frame: pd.DataFrame) -> ResidualClassification:
    """Distinguish persistent signed bias from noise without claiming a cause."""

    residual = residual_frame["residual_c"].to_numpy(dtype=float)
    median = float(np.median(residual))
    mad = robust_mad(residual)
    autocorrelation = lag_autocorrelation(residual)
    scaled = max(1.4826 * mad, 0.05)
    signed_fraction = max(float(np.mean(residual >= 0.0)), float(np.mean(residual <= 0.0)))
    if abs(median) >= scaled and signed_fraction >= 0.7:
        return ResidualClassification(
            "persistent_bias", median, mad, autocorrelation,
            "signed median exceeds robust spread and retains one sign for at least 70% of samples",
        )
    if abs(median) < scaled and (autocorrelation is None or abs(autocorrelation) < 0.25):
        return ResidualClassification(
            "noise_dominant", median, mad, autocorrelation,
            "signed median is small relative to robust spread and serial dependence is weak",
        )
    return ResidualClassification(
        "unclassified", median, mad, autocorrelation,
        "pattern is neither a clear persistent bias nor weakly correlated noise",
    )


def block_bootstrap_interval(
    values: Iterable[float],
    statistic: callable = np.mean,
    block_size: int = 24,
    replicates: int = 500,
    confidence: float = 0.95,
    seed: int = 20260718,
) -> BootstrapInterval:
    """Deterministic moving-block bootstrap for a time-correlated scalar.

    The caller must pass one contiguous regime segment; the function does not
    silently bridge a data gap.
    """

    data = np.asarray(tuple(values), dtype=float)
    if len(data) == 0 or not np.isfinite(data).all():
        raise ValueError("bootstrap values must be non-empty and finite.")
    if not 1 <= block_size <= len(data) or replicates < 20 or not 0.0 < confidence < 1.0:
        raise ValueError("invalid block bootstrap configuration.")
    rng = np.random.default_rng(seed)
    starts = np.arange(len(data) - block_size + 1)
    samples = np.empty(replicates, dtype=float)
    for replicate in range(replicates):
        parts: list[np.ndarray] = []
        length = 0
        while length < len(data):
            start = int(rng.choice(starts))
            part = data[start : start + block_size]
            parts.append(part)
            length += len(part)
        samples[replicate] = float(statistic(np.concatenate(parts)[: len(data)]))
    alpha = (1.0 - confidence) / 2.0
    return BootstrapInterval(
        estimate=float(statistic(data)),
        lower=float(np.quantile(samples, alpha)),
        upper=float(np.quantile(samples, 1.0 - alpha)),
        confidence=confidence,
        replicates=replicates,
        block_size=block_size,
    )


def fit_regime_bias(train_residual: pd.DataFrame, regime_column: str) -> dict[object, float]:
    """Fit a strictly train-only additive residual correction per known regime."""

    if regime_column not in train_residual.columns:
        raise ValueError(f"Missing regime column: {regime_column}")
    return {
        regime: float(values["residual_c"].median())
        for regime, values in train_residual.groupby(regime_column, dropna=False)
    }


def apply_regime_bias(
    residual_frame: pd.DataFrame, regime_column: str, fitted_bias: Mapping[object, float]
) -> pd.DataFrame:
    """Apply a train-learned correction; unknown regimes remain explicitly uncorrected."""

    if regime_column not in residual_frame.columns:
        raise ValueError(f"Missing regime column: {regime_column}")
    result = residual_frame.copy()
    result["regime_bias_c"] = result[regime_column].map(fitted_bias).fillna(0.0)
    result["Tin_estimated_regime_corrected"] = result["Tin_estimated"] + result["regime_bias_c"]
    result["residual_regime_corrected_c"] = (
        result["Tin_measured"] - result["Tin_estimated_regime_corrected"]
    )
    return result


def rank_association_hypotheses(
    residual_frame: pd.DataFrame,
    covariates: Iterable[str],
    bootstrap_replicates: int = 300,
) -> list[AssociationHypothesis]:
    """Rank associations only; names and text deliberately avoid causal claims."""

    hypotheses: list[AssociationHypothesis] = []
    for covariate in covariates:
        if covariate not in residual_frame.columns:
            continue
        pair = residual_frame[["residual_c", covariate]].dropna()
        if len(pair) < 30:
            continue
        rho = float(spearmanr(pair["residual_c"], pair[covariate]).statistic)
        interval = block_bootstrap_interval(
            pair[["residual_c", covariate]].to_numpy(),
            statistic=lambda array: spearmanr(array[:, 0], array[:, 1]).statistic,
            block_size=min(24, len(pair)),
            replicates=bootstrap_replicates,
        )
        magnitude = abs(rho)
        classification = "strong_association" if magnitude >= 0.5 else "weak_association" if magnitude >= 0.2 else "no_clear_association"
        caveat = "association only; no causal attribution"
        if covariate.lower() in {"qhvac_w_a", "hvac", "hvac_state"}:
            caveat += "; Q interpretation retains the fixed Tin-block-A / meter-335546926 caveat"
        hypotheses.append(
            AssociationHypothesis(
                covariate=covariate,
                spearman_rho=rho,
                interval=interval,
                classification=classification,
                wording=caveat,
            )
        )
    return sorted(hypotheses, key=lambda hypothesis: abs(hypothesis.spearman_rho), reverse=True)


def run_validated_real_diagnostics(project_root: str | pd.PathLike[str], *args: object, **kwargs: object) -> None:
    """Gate for real M5 execution; current project intentionally raises here."""

    require_validated_m4(project_root)
    raise NotImplementedError(
        "A validated M4 residual artifact is required before a real diagnostic can be materialized."
    )
