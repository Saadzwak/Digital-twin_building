from thermal_twin.onboarding import OnboardingState, capabilities, questions_needed


def test_all_unknown_inputs_yield_exactly_five_questions() -> None:
    questions = questions_needed(OnboardingState())
    assert len(questions) == 5
    assert [question.key for question in questions] == [
        "thermal_boundary", "north_azimuth", "floor_heights", "glazing_geometry", "documented_surface_resistance"
    ]


def test_known_and_unknown_answers_change_only_their_own_dependencies() -> None:
    state = OnboardingState(
        thermal_boundary="known",
        north_azimuth="known",
        floor_heights="known",
        glazing_geometry="unknown",
        documented_surface_resistance="unknown",
    )
    assert [question.key for question in questions_needed(state)] == []
    enabled = capabilities(state)
    assert enabled["thermal_boundary"] is True
    assert enabled["facade_area"] is True
    assert enabled["volume"] is True
    assert enabled["glazing_ratio"] is False
    assert enabled["geometry_constrained_candidate"] is False


def test_not_asked_is_the_only_state_that_asks_a_question() -> None:
    state = OnboardingState(thermal_boundary="unknown")
    assert "thermal_boundary" not in [question.key for question in questions_needed(state)]
    assert capabilities(state)["thermal_boundary"] is False
