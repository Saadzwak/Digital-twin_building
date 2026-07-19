"""Public M9 materializer with full-bank dispersion and safe branch wording."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from . import dashboard_materialize_impl as _implementation
from .dashboard_contract import serialize_payload


_original_empirical_estimate = _implementation._empirical_estimate


def _empirical_estimate(value, values, unit, period, method, run_source):
    """Prevent a model-effective branch label from implying a physical wall."""

    safe_method = method.replace("paroi", "composant d’enveloppe indépendant")
    return _original_empirical_estimate(value, values, unit, period, safe_method, run_source)


_implementation._empirical_estimate = _empirical_estimate


def materialize_dashboard_payload(project_root: Path | str):
    """Write the M9 payload, retaining dispersion for all nineteen labels."""

    root = Path(project_root).resolve()
    payload = _implementation.materialize_dashboard_payload(root)
    starts_path = root / "runs" / "m4" / "multistart" / "all_starts.json"
    merged = json.loads(starts_path.read_text(encoding="utf-8"))
    summaries = tuple(sorted(merged["basin_summaries"], key=lambda row: int(row["model_index"])))
    payload = replace(payload, basin_dispersion=summaries)
    target = root / "runs" / "m9" / "dashboard_payload.json"
    target.write_text(json.dumps(serialize_payload(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload
