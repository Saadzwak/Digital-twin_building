from pathlib import Path

from thermal_twin.diagnostics import run_validated_real_diagnostics
from thermal_twin.validation_gate import load_m4_verdict


def test_real_gap_aware_m5_metrics_disclose_their_statistic_segment() -> None:
    root = Path(__file__).resolve().parents[1]
    if load_m4_verdict(root).get("validated") is not True:
        return
    payload = run_validated_real_diagnostics(root)
    for metric in payload["metrics"].values():
        assert metric["contiguous_segment_n"] <= metric["n_samples"]
        assert "longest contiguous" in metric["metric_segment_policy"]
