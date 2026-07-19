import hashlib
import json
import math
from pathlib import Path

import pandas as pd

SINGLE_START_HISTORY_SHA256 = "e8bd817d5bc522bd38b664204eb2dbdb7c173dd761c3996f783397e934198752"
# Le CSV est régénérable par le script gelé ; entre exécutions la trajectoire
# numérique peut varier de quelques ulp (H-M4-05), d'où une tolérance explicite
# au lieu d'une égalité bit à bit.
REGENERATION_TOLERANCE = 1e-9


def test_single_start_history_is_preserved_and_multistart_replaces_only_the_gate() -> None:
    root = Path(__file__).resolve().parents[1]
    history_path = root / "runs" / "m4" / "single_start_verdict.json"
    assert hashlib.sha256(history_path.read_bytes()).hexdigest() == SINGLE_START_HISTORY_SHA256
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert history["conclusion"] == "FAILED_REPRODUCTION_DO_NOT_USE_FOR_PRODUCT_CLAIMS"
    pinned = history["primary_criteria"]["std_4r3c"]
    assert pinned["observed_validation_rmse"] == 5.007034573212
    assert pinned["observed_validation_bic"] == 4774.862180096648
    assert pinned["observed_test_rmse"] == 0.849648062482

    rows = pd.read_csv(root / "runs" / "m4" / "reproduction_19_models.csv")
    verdict = json.loads((root / "runs" / "m4" / "verdict.json").read_text(encoding="utf-8"))
    assert len(rows) == 19
    assert rows["model"].nunique() == 19
    selected = rows.loc[rows["model"] == "STD_4R3C_two_masses_plus_air_shunt"].iloc[0]
    assert math.isclose(selected["validation_rmse"], pinned["observed_validation_rmse"], rel_tol=REGENERATION_TOLERANCE)
    assert math.isclose(selected["validation_bic"], pinned["observed_validation_bic"], rel_tol=REGENERATION_TOLERANCE)
    assert math.isclose(selected["test_rmse"], pinned["observed_test_rmse"], rel_tol=REGENERATION_TOLERANCE)
    assert set(rows.loc[rows["duplicate_of"].notna(), "model"]) == {
        "STD_1R1C", "STD_2R2C_air_mass", "STD_3R3C_two_masses_series"
    }
    multi = root / "runs" / "m4" / "multistart" / "all_starts.json"
    if not multi.is_file():
        assert verdict["validated"] is False
        return
    merged = json.loads(multi.read_text(encoding="utf-8"))
    count = int(merged["config"]["n_starts"])
    assert count == 32
    assert len(merged["outcomes"]) == 19 * count
    assert len(merged["selected"]) == len(merged["basin_summaries"]) == 19
    assert verdict["validated"] is True
    assert verdict["validation_route"] in {"A", "B"}
    oracle = json.loads((root / "runs" / "m4" / "multistart" / "notebook_parameter_oracle.json").read_text(encoding="utf-8"))
    assert oracle["passed"] is True
