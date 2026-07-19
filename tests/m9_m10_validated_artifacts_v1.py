from __future__ import annotations

import json
from pathlib import Path

import pytest

from thermal_twin.constrained_chat import answer, write_chat_context
from thermal_twin.dashboard_materialize import materialize_dashboard_payload
from thermal_twin.diagnostics import run_validated_real_diagnostics


def test_validated_dashboard_and_chat_surface_only_sourced_uncertain_cards() -> None:
    root = Path(__file__).resolve().parents[1]
    verdict = json.loads((root / "runs" / "m4" / "verdict.json").read_text(encoding="utf-8"))
    if verdict.get("validated") is not True:
        pytest.skip("M4 multi-start A/B artifact has not been materialized yet.")
    run_validated_real_diagnostics(root)
    payload = materialize_dashboard_payload(root)
    write_chat_context(root)
    assert len(payload.basin_dispersion) == 19
    assert payload.initialization_sensitive is (verdict["validation_route"] == "B")
    for estimate in payload.identity_metrics + payload.effective_path_losses + payload.conditional_counterfactuals:
        assert estimate.lower <= estimate.value <= estimate.upper
        assert estimate.run_source == payload.run_source
    metric_card = answer("Quel est le RMSE de validation ?", root)
    assert metric_card.kind == "answer"
    assert metric_card.estimates
    if verdict["validation_route"] == "B":
        assert "sensible à l’initialisation" in metric_card.text
    assert answer("Quelle est la perte du mur nord ?", root).kind == "refusal"
    assert answer("Raconte-moi une blague", root).kind == "refusal"
