"""Residual diagnostics with a local-scale regime-break detector.

The first implementation is retained in ``diagnostics_legacy`` for audit
history.  This public module overrides only the tested break detector: a global
MAD can be inflated by the very two-regime mixture it is meant to detect.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .diagnostics_legacy import (
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
    run_validated_real_diagnostics,
)


def detect_regime_breaks(
    residual_frame: pd.DataFrame,
    window: int = 24,
    threshold_mad: float = 3.0,
    minimum_separation: int = 24,
) -> list[RegimeBreak]:
    """Detect local robust-median shifts without crossing missing-data gaps.

    The scale is calculated from each adjacent before/after window.  This
    prevents a global two-regime mixture from masking its own discontinuity.
    A 0.05 °C floor avoids treating numerical round-off as evidence.
    """

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
            local_scale = max(
                1.4826 * robust_mad(before_values),
                1.4826 * robust_mad(after_values),
                0.05,
            )
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


__all__ = [
    "AssociationHypothesis", "BootstrapInterval", "RESIDUAL_CONVENTION", "ResidualClassification",
    "RegimeBreak", "apply_regime_bias", "block_bootstrap_interval", "build_residual_frame",
    "classify_residual", "detect_regime_breaks", "fit_regime_bias", "lag_autocorrelation",
    "rank_association_hypotheses", "robust_mad", "run_validated_real_diagnostics",
]
