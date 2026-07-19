from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from thermal_twin.diagnostics import (
    apply_regime_bias,
    block_bootstrap_interval,
    build_residual_frame,
    classify_residual,
    detect_regime_breaks,
    fit_regime_bias,
    run_validated_real_diagnostics,
)
from thermal_twin.validation_gate import M4ValidationError, load_m4_verdict


def test_residual_sign_and_gap_segmentation_are_immutable() -> None:
    index = pd.DatetimeIndex(["2021-01-01T00:00:00Z", "2021-01-01T01:00:00Z", "2021-01-01T04:00:00Z"])
    frame = build_residual_frame(index, [20.0, 19.0, 22.0], [19.0, 20.0, 21.0])
    assert frame["residual_c"].tolist() == [1.0, -1.0, 1.0]
    assert frame["segment_id"].tolist() == [0, 0, 1]
    assert frame["gap_before"].tolist() == [False, False, True]


def test_known_regime_break_is_detected_without_crossing_gap() -> None:
    index = pd.date_range("2021-01-01", periods=120, freq="h", tz="UTC")
    residual = np.r_[np.zeros(60), np.full(60, 3.0)]
    frame = build_residual_frame(index, residual, np.zeros_like(residual))
    breaks = detect_regime_breaks(frame, window=12, threshold_mad=3.0, minimum_separation=12)
    assert breaks
    assert 55 <= (breaks[0].timestamp - index[0]).total_seconds() / 3600 <= 65
    assert classify_residual(frame).label == "unclassified"


def test_bias_and_noise_classifications_are_distinct() -> None:
    index = pd.date_range("2021-01-01", periods=120, freq="h", tz="UTC")
    bias = build_residual_frame(index, 2.0 + 0.05 * np.sin(np.arange(120)), np.zeros(120))
    rng = np.random.default_rng(42)
    noise = build_residual_frame(index, rng.normal(0.0, 1.0, 120), np.zeros(120))
    assert classify_residual(bias).label == "persistent_bias"
    assert classify_residual(noise).label == "noise_dominant"


def test_block_bootstrap_is_deterministic() -> None:
    values = np.sin(np.linspace(0.0, 10.0, 120))
    first = block_bootstrap_interval(values, block_size=12, replicates=100, seed=7)
    second = block_bootstrap_interval(values, block_size=12, replicates=100, seed=7)
    assert first == second
    assert first.lower <= first.estimate <= first.upper


def test_regime_calibration_reads_only_train_residuals() -> None:
    train = build_residual_frame(pd.date_range("2021-01-01", periods=4, freq="h", tz="UTC"), [2.0, 2.0, 4.0, 4.0], [0.0] * 4)
    train["regime"] = ["cold", "cold", "warm", "warm"]
    held_out = build_residual_frame(pd.date_range("2021-02-01", periods=2, freq="h", tz="UTC"), [100.0, -100.0], [0.0, 0.0])
    held_out["regime"] = ["cold", "warm"]
    fitted = fit_regime_bias(train, "regime")
    assert fitted == {"cold": 2.0, "warm": 4.0}
    corrected = apply_regime_bias(held_out, "regime", fitted)
    assert corrected["regime_bias_c"].tolist() == [2.0, 4.0]


def test_real_diagnostics_are_gated_or_materialized_from_validated_m4() -> None:
    root = Path(__file__).resolve().parents[1]
    verdict = load_m4_verdict(root)
    if verdict.get("validated") is not True:
        with pytest.raises(M4ValidationError, match="not validated"):
            run_validated_real_diagnostics(root)
        return
    result = run_validated_real_diagnostics(root)
    assert result["residual_convention"] == "Tin_measured - Tin_estimated"
    assert result["m4_validation_route"] in {"A", "B"}
    assert set(result["metrics"]) == {"train", "validation", "test"}
