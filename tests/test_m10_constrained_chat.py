from pathlib import Path

import pytest

from thermal_twin.constrained_chat import AnswerCard, answer, classify_intent
from thermal_twin.dashboard_contract import IntervalEstimate
from thermal_twin.validation_gate import load_m4_verdict


def test_per_wall_causal_and_savings_requests_are_refused_explicitly() -> None:
    root = Path(__file__).resolve().parents[1]
    for query in ("Quelle est la perte du mur nord ?", "Quelle est la cause de la dérive ?", "Quelle économie vais-je faire ?"):
        card = answer(query, root)
        assert card.kind == "refusal"
        assert "ne peux pas" in card.text
        assert card.estimates == ()


def test_current_model_query_is_blocked_or_answered_only_from_a_validated_context() -> None:
    root = Path(__file__).resolve().parents[1]
    card = answer("Quel est le RMSE de validation ?", root)
    if load_m4_verdict(root).get("validated") is not True:
        assert card.kind == "blocked"
        assert card.run_source is None
        assert card.estimates == ()
        return
    assert card.kind == "answer"
    assert card.run_source
    assert card.estimates


def test_answer_cards_require_a_run_source_and_refusal_cards_cannot_leak_numbers() -> None:
    with pytest.raises(ValueError, match="run source"):
        AnswerCard(kind="answer", text="x", run_source=None)
    estimate = IntervalEstimate(1.0, 0.5, 1.5, "°C", "test", "bootstrap", "run-x")
    with pytest.raises(ValueError, match="cannot expose"):
        AnswerCard(kind="refusal", text="x", run_source=None, estimates=(estimate,))
    assert classify_intent("Donne la topologie") == "topology"
