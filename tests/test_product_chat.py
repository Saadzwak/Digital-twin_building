"""Product chat: sourced answers, useful refusals with served alternatives."""

from pathlib import Path

import pytest

from thermal_twin.live_run import DemoConfig, load_product_payload, run_live_pipeline
from thermal_twin.product_chat import product_answer, serialize_product_card

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def ensure_payload() -> None:
    if load_product_payload(ROOT) is not None:
        return
    generator = run_live_pipeline(
        ROOT, DemoConfig(n_starts=2, structure_names=("LADDER_1R1C",), journal_name="latest"))
    try:
        while True:
            next(generator)
    except StopIteration:
        return


def test_drift_question_gets_a_dated_sourced_answer() -> None:
    card = product_answer("When does the building drift?", ROOT)
    assert card.kind == "answer"
    assert card.run_source is not None
    assert "2021" in card.text


def test_wall_question_is_refused_with_explanation_and_alternative() -> None:
    card = product_answer("What is the loss of the north wall?", ROOT)
    assert card.kind == "refusal"
    assert "single average indoor temperature" in card.text
    assert card.alternative_text is not None
    assert card.alternative_estimates, "the global heat-loss alternative must be served with its interval"
    assert card.alternative_estimates[0].unit == "W/°C"


def test_guaranteed_savings_are_refused_with_conditional_alternative() -> None:
    card = product_answer("How much money will I save, guaranteed?", ROOT)
    assert card.kind == "refusal"
    assert card.alternative_text is not None and "%" in card.alternative_text


def test_unrelated_question_gets_a_helpful_refusal() -> None:
    card = product_answer("Tell me a joke", ROOT)
    assert card.kind == "refusal"
    assert card.scope_note is not None and "drift" in card.scope_note


def test_cards_serialize_without_loss() -> None:
    card = product_answer("What is the heat-loss level?", ROOT)
    assert card.kind == "answer"
    serialized = serialize_product_card(card)
    assert serialized["run_source"] == card.run_source
    assert serialized["estimates"][0]["unit"] == "W/°C"
