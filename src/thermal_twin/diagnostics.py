"""M5 public API with explicit gap-aware metric provenance."""

from __future__ import annotations

import json
from pathlib import Path

from . import diagnostics_m5_impl as _implementation
from .diagnostics_m5_impl import *  # noqa: F401,F403,E402


_SEGMENT_POLICY = (
    "Bootstrap interval statistics use only the longest contiguous observed sequence; "
    "n_samples remains the full split count and contiguous_segment_n is the exact statistic sample count."
)


def run_validated_real_diagnostics(project_root: str | Path) -> dict[str, object]:
    """Materialize M5 and disclose why a gap-aware residual RMSE can differ from M4."""

    payload = _implementation.run_validated_real_diagnostics(project_root)
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("M5 diagnostics did not produce split metrics.")
    for split_metrics in metrics.values():
        if not isinstance(split_metrics, dict):
            raise ValueError("M5 diagnostics contain an invalid split metric record.")
        split_metrics["metric_segment_policy"] = _SEGMENT_POLICY
    root = Path(project_root).resolve()
    target = root / "runs" / "m5" / "diagnostic.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return payload


__all__ = [name for name in _implementation.__all__ if name != "run_validated_real_diagnostics"] + [
    "run_validated_real_diagnostics"
]
