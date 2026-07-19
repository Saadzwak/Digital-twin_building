"""Backend web layer: sanitization, topology graphs, selection consistency."""

import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

from thermal_twin.sanitize import clean, finite_series
from thermal_twin.building_geometry import load_massing
import engine


def test_clean_replaces_non_finite_with_none():
    payload = {"a": float("nan"), "b": float("inf"), "c": -float("inf"), "d": 3.5,
               "list": [1.0, float("nan"), {"x": np.float64("nan")}], "np_int": np.int64(4)}
    cleaned = clean(payload)
    assert cleaned["a"] is None and cleaned["b"] is None and cleaned["c"] is None
    assert cleaned["d"] == 3.5
    assert cleaned["list"][1] is None and cleaned["list"][2]["x"] is None
    assert cleaned["np_int"] == 4 and isinstance(cleaned["np_int"], int)


def test_finite_series_drops_non_finite_points():
    pairs = [("a", 1.0), ("b", float("nan")), ("c", float("inf")), ("d", 2)]
    kept = finite_series(pairs)
    assert kept == [["a", 1.0], ["d", 2]]


def test_no_non_finite_survives_clean_on_nested_structure():
    def has_bad(v):
        if isinstance(v, float):
            return not math.isfinite(v)
        if isinstance(v, dict):
            return any(has_bad(x) for x in v.values())
        if isinstance(v, list):
            return any(has_bad(x) for x in v)
        return False
    assert not has_bad(clean({"k": [float("nan"), float("inf"), {"z": float("-inf")}]}))


def test_topology_graphs_cover_all_19_with_valid_structure():
    graphs = engine.all_topology_graphs()
    assert len(graphs) == 19
    g = graphs["STD_4R3C_two_masses_plus_air_shunt"]
    assert g["n_parameters"] == 8
    assert sum(1 for n in g["nodes"] if n["kind"] == "air") == 1
    assert len(g["resistances"]) == 4 and len(g["capacities"]) == 3
    # every resistance references a real node or the outdoor rail
    node_ids = {n["id"] for n in g["nodes"]}
    for r in g["resistances"]:
        assert r["from"] in node_ids
        assert r["to"] == "outdoor" or r["to"] in node_ids


def test_geometry_artifact_is_present_and_honest():
    massing = load_massing(ROOT)
    assert massing is not None
    assert len(massing["footprint"]) >= 4
    assert massing["n_floors"] == 6
    assert "volume" in massing["honesty_note"].lower()
    for point in massing["footprint"]:
        assert 0.0 <= point[0] <= 1.0 and 0.0 <= point[1] <= 1.0


def test_reference_selection_is_consistent_with_operating_twin():
    result = engine.record_reference(ROOT)  # cached from server startup
    payload = result["payload"]
    assert payload["selection"]["headline_model"] == payload["twin"]["structure_label"]
    assert payload["twin"]["consistent_with_selection"] is True
    # the automated bank pick is surfaced (declared), not hidden
    assert payload["selection"]["bank_auto_pick"]["model"]
    assert payload["selection"]["twin_is_bank_selection"] is False
    assert "explorer" in payload["selection"]["explainer"].lower() or "explore" in payload["selection"]["explainer"].lower()


def test_uploaded_csv_with_renamed_tz_aware_columns_parses():
    import pandas as pd
    from thermal_twin.live_run import prepare_uploaded_csv
    ref = pd.read_csv(ROOT / "data" / "processed" / "hourly_reference.csv")
    renamed = ref.rename(columns={"Date": "timestamp", "Tin": "T_interieur",
                                  "Tout": "T_exterieur", "Qhvac_W_A": "HVAC_power"})
    content = renamed.to_csv(index=False).encode("utf-8")
    hourly, provenance = prepare_uploaded_csv(content)
    assert len(hourly) > 8000
    assert list(hourly.columns) == ["Tin", "Tout", "Qhvac_W_A"]
    assert provenance["columns_used"]["tin"] == "T_interieur"
    assert not hourly.isna().any().any()
