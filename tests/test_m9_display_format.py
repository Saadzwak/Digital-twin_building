from thermal_twin.dashboard_ui import _shown_number


def test_bic_is_rendered_to_one_decimal_while_raw_values_remain_in_run_artifacts() -> None:
    assert _shown_number(4578.578337, "BIC") == "4578.6"
    assert _shown_number(4.682382, "°C") != "4.7"
