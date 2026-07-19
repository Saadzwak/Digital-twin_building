"""Full-year open-loop drift analysis for the selected effective model.

The annual figure of the source article is reproduced live: one open-loop
simulation over the whole measured year, the measured-minus-estimated
residual, the detected regime switch and the signed cumulative gap.  The
detector is the frozen M5 one; nothing here refits or recalibrates.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .diagnostics import build_residual_frame, detect_regime_breaks
from .fast_sim import simulate_open_loop_fast
from .rc_core import RCTopology


@dataclass(frozen=True)
class AnnualDrift:
    frame: pd.DataFrame
    daily: pd.DataFrame
    breaks: tuple[dict[str, object], ...]
    principal_break: dict[str, object] | None
    structural_switch: dict[str, object] | None
    cumulative_final_c_h: float
    direction: str
    split_bounds: dict[str, str]


def structural_switch(
    daily_residual: pd.Series,
    train_hours: int,
    z_threshold: float = 3.0,
    persistence_days: int = 14,
) -> dict[str, object] | None:
    """First date where the daily residual leaves the calibrated band and stays out.

    The band is the train-period daily median ± ``z_threshold`` robust standard
    deviations (1.4826 × MAD).  A switch requires ``persistence_days``
    consecutive days outside the band, so single cold snaps do not qualify.
    """

    daily = daily_residual.dropna()
    if len(daily) < persistence_days + 30:
        return None
    train_days = max(30, train_hours // 24)
    train = daily.iloc[:train_days]
    center = float(train.median())
    scale = 1.4826 * float((train - center).abs().median())
    if scale <= 0:
        return None
    z = (daily - center) / scale

    def _first_persistent_excursion(threshold: float) -> pd.Timestamp | None:
        outside = z.abs() > threshold
        run_start: pd.Timestamp | None = None
        run_length = 0
        for timestamp, is_out in outside.items():
            if is_out:
                run_length += 1
                if run_start is None:
                    run_start = timestamp
                if run_length >= persistence_days:
                    return run_start
            else:
                run_start = None
                run_length = 0
        return None

    rupture = _first_persistent_excursion(z_threshold)
    if rupture is None:
        return None
    # Onset = start of the contiguous |z| > 1 excursion that leads to the
    # rupture, walked backwards from the rupture date itself.
    positions = daily.index.get_indexer([rupture])
    position = int(positions[0])
    z_values = z.to_numpy()
    onset_position = position
    while onset_position > 0 and abs(z_values[onset_position - 1]) > 1.0:
        onset_position -= 1
    onset = daily.index[onset_position] if onset_position < position else None
    after = daily.loc[rupture:]
    mean_after = float(after.mean())
    return {
        "date": str(rupture.date()),
        "timestamp": str(rupture),
        "onset_date": str(onset.date()) if onset is not None else None,
        "mean_residual_after_c": mean_after,
        "offset_from_calibrated_c": mean_after - center,
        "sign": "below" if mean_after < center else "above",
        "z_threshold": z_threshold,
        "persistence_days": persistence_days,
        "train_band_center_c": center,
        "train_band_halfwidth_c": z_threshold * scale,
    }


def _principal_break(breaks: list, index: pd.DatetimeIndex) -> dict[str, object] | None:
    """Prefer the first break after the training period; fall back to largest.

    Training residuals are near-zero by construction, so a shift detected
    inside training is calibration noise rather than the seasonal switch the
    user needs to see.  If no post-training break exists, the largest one is
    reported unchanged.
    """

    if not breaks:
        return None
    training_end = index[0] + pd.DateOffset(months=9)
    after = [item for item in breaks if item.timestamp >= training_end]
    pool = after if after else breaks
    chosen = max(pool, key=lambda item: abs(item.median_shift_c))
    return {
        "timestamp": str(chosen.timestamp),
        "median_shift_c": float(chosen.median_shift_c),
        "robust_scale_c": float(chosen.robust_scale_c),
        "evidence": chosen.evidence,
        "in_training_period": bool(chosen.timestamp < training_end),
    }


def compute_annual_drift(
    topology: RCTopology,
    parameters_log: np.ndarray,
    hourly: pd.DataFrame,
    dt_seconds: float = 3600.0,
    train_hours: int = 6460,
) -> AnnualDrift:
    tin = hourly["Tin"].to_numpy(dtype=float)
    tout = hourly["Tout"].to_numpy(dtype=float)
    q_hvac = hourly["Qhvac_W_A"].to_numpy(dtype=float)
    estimated = simulate_open_loop_fast(topology, tout, q_hvac, dt_seconds, np.asarray(parameters_log, dtype=float), tin[0])
    frame = build_residual_frame(hourly.index, tin, estimated)
    frame["cumulative_gap_c_h"] = frame["residual_c"].cumsum()
    breaks = detect_regime_breaks(frame)
    principal = _principal_break(breaks, pd.DatetimeIndex(hourly.index))
    switch = structural_switch(frame["residual_c"].resample("1D").mean(), train_hours=train_hours)

    daily = pd.DataFrame(
        {
            "Tin_measured": frame["Tin_measured"].resample("1D").mean(),
            "Tin_estimated": frame["Tin_estimated"].resample("1D").mean(),
            "residual_c": frame["residual_c"].resample("1D").mean(),
        }
    ).dropna(how="all")
    daily["cumulative_gap_c_h"] = frame["cumulative_gap_c_h"].resample("1D").last().reindex(daily.index)

    final_gap = float(frame["cumulative_gap_c_h"].iloc[-1])
    if abs(final_gap) < 1e-9:
        direction = "neutral"
    elif final_gap > 0:
        direction = "the building stays warmer than the calibrated behaviour"
    else:
        direction = "the building stays colder than the calibrated behaviour"

    index = pd.DatetimeIndex(hourly.index)
    train_end = index[0] + pd.DateOffset(months=9)
    validation_end = index[0] + pd.DateOffset(months=11)
    serialized_breaks = tuple(
        {
            "timestamp": str(item.timestamp),
            "median_shift_c": float(item.median_shift_c),
            "robust_scale_c": float(item.robust_scale_c),
            "evidence": item.evidence,
        }
        for item in breaks
    )
    return AnnualDrift(
        frame=frame,
        daily=daily,
        breaks=serialized_breaks,
        principal_break=principal,
        structural_switch=switch,
        cumulative_final_c_h=final_gap,
        direction=direction,
        split_bounds={
            "train_end": str(train_end),
            "validation_end": str(validation_end),
        },
    )


def drift_summary(drift: AnnualDrift) -> dict[str, object]:
    """Serializable summary for the product journal and the chat."""

    switch = drift.structural_switch
    if switch is not None:
        onset = switch.get("onset_date")
        onset_clause = (
            f"The drift is visible from {onset}; " if onset and onset != switch["date"] else ""
        )
        message = (
            f"{onset_clause}from {switch['date']}, the building stops behaving like the calibrated model: "
            f"the measured temperature stays {switch['sign']} the expected behaviour "
            f"({switch['offset_from_calibrated_c']:+.1f} °C on average afterwards). "
            "The gap is structural, not noise."
        )
    else:
        message = (
            "No sustained departure from the calibrated band is detected over the year; "
            "this is not proof that no drift exists."
        )
    return {
        "n_hours": int(len(drift.frame)),
        "structural_switch": switch,
        "message": message,
        "principal_break": drift.principal_break,
        "n_breaks_detected": len(drift.breaks),
        "cumulative_final_c_h": drift.cumulative_final_c_h,
        "direction": drift.direction,
        "split_bounds": drift.split_bounds,
        "residual_convention": "Tin_measured - Tin_estimated",
        "note": "Open-loop simulation over the whole year; the gap is structural if it persists after the calibration period.",
    }
