"""Renovation costing: deterministic, matches the reference figures, ranked by ROI."""

from pathlib import Path

from thermal_twin.renovation import (
    BUILDING,
    compute_exploitation,
    interpretation,
    renovation_report,
)

ROOT = Path(__file__).resolve().parents[1]


def test_deep_retrofit_reproduces_reference_co2_and_cost():
    # F -> B on the ground-footprint area with the gas factor reproduces the
    # documented ConX figures (1727 tCO2 over 30 yr, €650,400).
    report = renovation_report(ROOT)
    deep = next(s for s in report["scenarios"] if s["key"] == "deep_retrofit")
    assert abs(deep["co2_avoided_t_30y"] - BUILDING["conx_co2_avoided_t_30y"]) <= 2
    assert deep["cost_eur"] == int(BUILDING["conx_cost_estimate_eur"])


def test_exploitation_is_deterministic():
    a = compute_exploitation(1084.0, "F", "B", 324.0, "gas")
    assert round(a["avoided_horizon_kg"] / 1000.0) == 1727


def test_scenarios_ranked_by_payback_and_all_virtuous():
    report = renovation_report(ROOT)
    paybacks = [s["payback_years"] for s in report["scenarios"]]
    assert paybacks == sorted(paybacks)
    for s in report["scenarios"]:
        assert s["net_co2_t_30y"] < 0  # carbon-virtuous over 30 years
        assert s["savings_eur_year"] > 0 and s["cost_eur"] > 0


def test_aides_and_regulation_present_and_english():
    report = renovation_report(ROOT)
    codes = {a["code"] for a in report["aides"]}
    assert {"ECO_PLS", "CEE_BS_PASSOIRE", "ANRU"} <= codes
    # Éco-PLS is a loan, CEE a grant
    assert next(a for a in report["aides"] if a["code"] == "ECO_PLS")["kind"] == "loan"
    assert next(a for a in report["aides"] if a["code"] == "CEE_BS_PASSOIRE")["kind"] == "grant"
    assert any("Energy sieve" in c["label"] for c in report["regulation"])


def test_interpretation_returns_three_leads():
    r = interpretation(0.96, {"date": "2021-11-15", "onset_date": "2021-10-03", "offset_from_calibrated_c": -10.4}, 151.0)
    assert len(r["leads"]) == 3
    assert "ventilation" in r["leads"][0]["reading"].lower()
