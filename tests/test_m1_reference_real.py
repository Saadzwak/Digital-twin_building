from pathlib import Path

import numpy as np

from thermal_twin.reference_ingestion import prepare_reference_dataset, split_reference_months


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_reference_data_pipeline_matches_notebook_counts_and_anchors() -> None:
    prepared = prepare_reference_dataset(PROJECT_ROOT)
    hourly = prepared.hourly
    splits = split_reference_months(hourly)

    assert prepared.meter_id == "335546926"
    assert prepared.sensor_count == 49
    assert prepared.selected_sensor_observations == 2_115_936
    assert prepared.unique_tin_timestamps == 847_227
    assert np.isclose(prepared.energy_interval_seconds, 599.016, atol=1e-12)
    assert np.isclose(prepared.q_clip_lower_w, 234.76000641051326, atol=1e-6)
    assert np.isclose(prepared.q_clip_upper_w, 14527.371764694082, atol=1e-6)
    assert len(hourly) == 8604
    assert str(hourly.index.min()) == "2021-01-01 00:00:00+00:00"
    assert str(hourly.index.max()) == "2021-12-31 22:00:00+00:00"
    assert hourly.index.is_monotonic_increasing
    assert not hourly.index.has_duplicates
    assert not hourly.isna().any().any()
    assert {name: len(part) for name, part in splits.items()} == {
        "train": 6460,
        "validation": 1464,
        "test": 680,
    }
    first = hourly.iloc[0]
    last = hourly.iloc[-1]
    assert np.isclose(first["Tin"], 22.662610514084736, atol=1e-10)
    assert np.isclose(first["Tout"], 3.2898199507575754, atol=1e-10)
    assert np.isclose(first["Qhvac_W_A"], 4126.548336514085, atol=1e-9)
    assert np.isclose(last["Tin"], 24.21681707497488, atol=1e-10)
    assert np.isclose(last["Tout"], 14.417952605309933, atol=1e-10)
    assert np.isclose(last["Qhvac_W_A"], 2743.714388574563, atol=1e-9)
