import json
from pathlib import Path

import pandas as pd


def test_executed_m4_artifact_preserves_all_labels_and_failure() -> None:
    root = Path(__file__).resolve().parents[1]
    rows = pd.read_csv(root / "runs" / "m4" / "reproduction_19_models.csv")
    verdict = json.loads((root / "runs" / "m4" / "verdict.json").read_text(encoding="utf-8"))
    assert len(rows) == 19
    assert rows["model"].nunique() == 19
    assert verdict["validated"] is False
    selected = rows.loc[rows["model"] == "STD_4R3C_two_masses_plus_air_shunt"].iloc[0]
    assert selected["validation_rmse"] == 5.007034573212
    assert selected["validation_bic"] == 4774.862180096648
    assert selected["test_rmse"] == 0.849648062482
    assert set(rows.loc[rows["duplicate_of"].notna(), "model"]) == {
        "STD_1R1C", "STD_2R2C_air_mass", "STD_3R3C_two_masses_series"
    }
