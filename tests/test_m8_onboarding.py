from thermal_twin.onboarding import OnboardingState, capabilities, questions_needed


def test_all_unknown_inputs_ask_only_the_four_nonextractable_facts() -> None:
    questions = questions_needed(OnboardingState())
    assert len(questions) == 4
    assert [question.key for question in questions] == [
        "thermal_boundary", "north_azimuth", "floor_heights", "glazing_geometry"
    ]
    assert len(questions) <= 5


def test_geometry_candidate_does_not_request_or_freeze_shared_surface_resistance() -> None:
    state = OnboardingState(
        thermal_boundary="known", north_azimuth="known", floor_heights="known", glazing_geometry="unknown"
    )
    assert [question.key for question in questions_needed(state)] == []
    enabled = capabilities(state)
    assert enabled["thermal_boundary"] is True
    assert enabled["facade_area"] is True
    assert enabled["volume"] is True
    assert enabled["glazing_ratio"] is False
    assert enabled["geometry_constrained_candidate"] is True


def test_not_asked_is_the_only_state_that_asks_a_question() -> None:
    state = OnboardingState(thermal_boundary="unknown")
    assert "thermal_boundary" not in [question.key for question in questions_needed(state)]
    assert capabilities(state)["thermal_boundary"] is False
