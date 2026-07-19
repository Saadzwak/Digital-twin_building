import pandas as pd

from thermal_twin.ingestion import PreparedDataset, split_reference_months


def test_month_split_is_calendar_based_and_preserves_gaps() -> None:
    index = pd.DatetimeIndex(
        [
            "2021-09-30T23:00:00Z",
            "2021-10-01T00:00:00Z",
            "2021-11-30T23:00:00Z",
            "2021-12-01T00:00:00Z",
        ]
    )
    hourly = pd.DataFrame(
        {"Tin": [1.0, 2.0, 3.0, 4.0], "Tout": [0.0] * 4, "Qhvac_W_A": [0.0] * 4},
        index=index,
    )
    splits = split_reference_months(hourly)
    assert list(splits) == ["train", "validation", "test"]
    assert [len(part) for part in splits.values()] == [1, 2, 1]


def test_public_prepared_dataset_refers_to_the_executed_reference_protocol() -> None:
    hourly = pd.DataFrame(
        {"Tin": [20.0], "Tout": [10.0], "Qhvac_W_A": [100.0]},
        index=pd.DatetimeIndex(["2021-01-01T00:00:00Z"]),
    )
    dataset = PreparedDataset(
        hourly=hourly,
        source_paths=None,  # type: ignore[arg-type] -- value-object-only test
        sensor_count=49,
        selected_sensor_observations=1,
        unique_tin_timestamps=1,
        meter_id="335546926",
        energy_interval_seconds=599.016,
        q_clip_lower_w=0.0,
        q_clip_upper_w=1.0,
    )
    assert dataset.hourly.iloc[0]["Tin"] == 20.0
    assert dataset.meter_id == "335546926"
