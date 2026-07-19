"""The live engine streams real events and journals a complete payload."""

from pathlib import Path

import pytest

from thermal_twin.live_run import DemoConfig, load_product_payload, run_live_pipeline

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def engine_run() -> tuple[list[dict], dict]:
    generator = run_live_pipeline(
        ROOT,
        DemoConfig(n_starts=2, structure_names=("LADDER_1R1C", "STD_2R1C_parallel_losses"),
                   journal_name="pytest"),
    )
    events: list[dict] = []
    try:
        while True:
            events.append(next(generator))
    except StopIteration as stop:
        return events, stop.value


def test_engine_emits_every_stage_in_order(engine_run) -> None:
    events, _ = engine_run
    kinds = [event["kind"] for event in events]
    for required in ("plan", "data_progress", "data_summary", "fit_start", "fit_done",
                     "structure_done", "selection", "twin", "drift_done", "scenario_done",
                     "payload_ready"):
        assert required in kinds
    assert kinds.index("data_summary") < kinds.index("fit_start")
    assert kinds.index("selection") < kinds.index("drift_done")
    assert kinds.index("drift_done") < kinds.index("payload_ready")


def test_engine_fit_events_reflect_real_per_start_progress(engine_run) -> None:
    events, _ = engine_run
    fits = [event for event in events if event["kind"] == "fit_done"]
    assert len(fits) == 4  # 2 structures x 2 starts
    assert all(event["elapsed_s"] > 0 for event in fits)
    assert all("train_mse" in event for event in fits)


def test_engine_payload_is_complete_and_journaled(engine_run) -> None:
    _, payload = engine_run
    assert payload["run_source"].startswith("demo-live-")
    assert payload["twin"]["structure_label"] == "STD_4R3C_two_masses_plus_air_shunt"
    assert payload["twin"]["metrics"]["validation_rmse"]["lower"] <= payload["twin"]["metrics"]["validation_rmse"]["value"]
    assert payload["drift"]["structural_switch"] is not None
    assert len(payload["scenarios"]) == 4
    assert payload["bank"]["rows"][0]["admissible"] in (True, False)
    journaled = load_product_payload(ROOT, journal_name="pytest")
    assert journaled is not None and journaled["run_source"] == payload["run_source"]
    assert (ROOT / "runs" / "demo" / "pytest" / "bank_journal.json").is_file()
    assert (ROOT / "runs" / "demo" / "pytest" / "drift_daily.csv").is_file()


def test_engine_reference_twin_reproduces_the_published_calibration(engine_run) -> None:
    _, payload = engine_run
    validation = payload["twin"]["metrics"]["validation_rmse"]["value"]
    test = payload["twin"]["metrics"]["test_rmse"]["value"]
    assert abs(validation - 4.682382) < 1e-3
    assert abs(test - 0.857599) < 1e-3


def test_engine_reports_heat_loss_non_robustness_between_equivalent_calibrations(engine_run) -> None:
    _, payload = engine_run
    heat_loss = payload["indicators"]["heat_loss"]
    assert payload["twin"]["companion_vectors"] >= 1
    assert heat_loss["spread_factor_between_calibrations"] > 3.0
    assert heat_loss["robust_between_calibrations"] is False
    assert "not robustly" in heat_loss["robustness_note"]
