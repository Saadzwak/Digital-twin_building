"""Structural-switch detection: synthetic truth and pinned real-data result."""

from pathlib import Path

import numpy as np
import pandas as pd

from thermal_twin.annual_drift import compute_annual_drift, drift_summary, structural_switch
from thermal_twin.multistart_impl import ORACLE_PHYSICAL_PARAMETERS_4R3C
from thermal_twin.topologies import STD_4R3C

ROOT = Path(__file__).resolve().parents[1]


def test_structural_switch_finds_a_known_synthetic_break() -> None:
    index = pd.date_range("2021-01-01", periods=365, freq="1D", tz="UTC")
    values = np.sin(np.arange(365) / 9.0)  # calibrated wobble, |z| stays small
    values[260:] -= 8.0
    switch = structural_switch(pd.Series(values, index=index), train_hours=200 * 24)
    assert switch is not None
    assert switch["date"] == str(index[260].date())
    assert switch["sign"] == "below"
    assert switch["offset_from_calibrated_c"] < -6.0


def test_structural_switch_absent_on_calibrated_noise() -> None:
    index = pd.date_range("2021-01-01", periods=365, freq="1D", tz="UTC")
    values = np.sin(np.arange(365) / 9.0)
    assert structural_switch(pd.Series(values, index=index), train_hours=200 * 24) is None


def test_annual_drift_on_reference_data_dates_the_autumn_switch() -> None:
    hourly = pd.read_csv(ROOT / "data" / "processed" / "hourly_reference.csv",
                         parse_dates=["Date"]).set_index("Date")
    theta = np.log(np.asarray(ORACLE_PHYSICAL_PARAMETERS_4R3C, dtype=float))
    drift = compute_annual_drift(STD_4R3C, theta, hourly, train_hours=6460)
    summary = drift_summary(drift)
    switch = summary["structural_switch"]
    assert switch is not None
    assert switch["date"] == "2021-11-15"
    assert switch["onset_date"] == "2021-10-03"
    assert switch["sign"] == "below"
    assert drift.cumulative_final_c_h < -10000.0
    assert "structural" in summary["message"]
