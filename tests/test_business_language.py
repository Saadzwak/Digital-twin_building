"""Surface wording: no jargon, magnitude gates honest."""

import numpy as np

from thermal_twin.business_language import (
    CANNOT_DISTINGUISH_TEXT,
    RELIABILITY_SURFACE_TEXT,
    assert_surface_text_clean,
    effective_heat_loss,
    format_heat_loss_sentence,
)
from thermal_twin.counterfactuals import SCENARIO_BANK
from thermal_twin.multistart_impl import ORACLE_PHYSICAL_PARAMETERS_4R3C
from thermal_twin.topologies import STD_4R3C, make_ladder


def test_fixed_surface_texts_are_free_of_identification_jargon() -> None:
    for text in (RELIABILITY_SURFACE_TEXT, CANNOT_DISTINGUISH_TEXT):
        assert_surface_text_clean(text)
    for scenario in SCENARIO_BANK:
        assert_surface_text_clean(scenario.title)
        assert_surface_text_clean(scenario.description)


def test_article_twin_heat_loss_is_physically_readable_and_direct_dominated() -> None:
    parameters = np.asarray(ORACLE_PHYSICAL_PARAMETERS_4R3C, dtype=float)
    level = effective_heat_loss(STD_4R3C, parameters[:4], float(parameters[-1]))
    assert level.physically_readable
    assert 50.0 < level.ua_w_per_k < 80.0
    assert level.direct_path_share is not None and level.direct_path_share > 0.9
    sentence = format_heat_loss_sentence(level)
    assert "W per °C" in sentence
    assert "direct" in sentence
    assert_surface_text_clean(sentence)


def test_degenerate_flywheel_calibration_is_reported_as_unreadable() -> None:
    ladder = make_ladder(1)
    level = effective_heat_loss(ladder, np.array([148.4]), 6.536)
    assert not level.physically_readable
    sentence = format_heat_loss_sentence(level)
    assert "not readable" in sentence
