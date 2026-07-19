from __future__ import annotations

import json
from pathlib import Path

import pytest

from thermal_twin.diagnostics import run_validated_real_diagnostics


def test_validated_m4_materializes_real_gap_aware_residual_diagnostics() -> None:
    root = Path(__file__).resolve().parents[1]
    verdict = json.loads((root / "runs" / "m4" / "verdict.json").read_text(encoding="utf-8"))
    if verdict.get("validated") is not True:
        pytest.skip("M4 multi-start A/B artifact has not been materialized yet.")
    payload = run_validated_real_diagnostics(root)
    assert payload["residual_convention"] == "Tin_measured - Tin_estimated"
    assert payload["m4_validation_route"] in {"A", "B"}
    assert set(payload["metrics"]) == {"train", "validation", "test"}
    assert payload["metrics"]["validation"]["residual_rmse_c"]["lower"] <= payload["metrics"]["validation"]["residual_rmse_c"]["estimate"] <= payload["metrics"]["validation"]["residual_rmse_c"]["upper"]
    assert payload["method"]["recalibration"].startswith("train-only")
    assert (root / "runs" / "m5" / "residual_train.csv").is_file()
