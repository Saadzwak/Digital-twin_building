"""Data contract ensuring every dashboard estimate is sourced and uncertain."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .validation_gate import require_validated_m4


@dataclass(frozen=True)
class IntervalEstimate:
    value: float
    lower: float
    upper: float
    unit: str
    period: str
    method: str
    run_source: str

    def __post_init__(self) -> None:
        if not self.unit or not self.period or not self.method or not self.run_source:
            raise ValueError("Every displayed estimate needs unit, period, method and run source.")
        if self.lower > self.upper or not self.lower <= self.value <= self.upper:
            raise ValueError("Estimate value must lie inside its uncertainty interval.")


@dataclass(frozen=True)
class DashboardPayload:
    """Validated-only product payload; no physical per-wall claim is permitted."""

    run_source: str
    topology_label: str
    convergence_status: str
    identity_limit: str
    effective_path_losses: tuple[IntervalEstimate, ...]
    dated_drift: tuple[IntervalEstimate, ...]
    conditional_counterfactuals: tuple[IntervalEstimate, ...]
    intervention_ranking: tuple[IntervalEstimate, ...]
    duplicate_labels: tuple[str, ...]

    def __post_init__(self) -> None:
        forbidden = ("wall", "façade", "facade", "paroi")
        for estimate in self.effective_path_losses:
            if any(word in estimate.method.lower() for word in forbidden):
                raise ValueError("Effective paths must not be relabeled as independently identified walls.")


def require_dashboard_access(project_root: Path | str) -> dict[str, object]:
    """Dashboard data is inaccessible unless M4’s machine-readable verdict passes."""

    return require_validated_m4(project_root)


def load_dashboard_payload(project_root: Path | str) -> DashboardPayload:
    """Load a payload only after the M4 gate; do not construct plausible fallback data."""

    require_dashboard_access(project_root)
    path = Path(project_root).resolve() / "runs" / "m9" / "dashboard_payload.json"
    if not path.is_file():
        raise FileNotFoundError(f"Validated dashboard payload is absent: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    to_estimate = lambda values: tuple(IntervalEstimate(**value) for value in values)
    return DashboardPayload(
        run_source=raw["run_source"],
        topology_label=raw["topology_label"],
        convergence_status=raw["convergence_status"],
        identity_limit=raw["identity_limit"],
        effective_path_losses=to_estimate(raw["effective_path_losses"]),
        dated_drift=to_estimate(raw["dated_drift"]),
        conditional_counterfactuals=to_estimate(raw["conditional_counterfactuals"]),
        intervention_ranking=to_estimate(raw["intervention_ranking"]),
        duplicate_labels=tuple(raw["duplicate_labels"]),
    )


def serialize_payload(payload: DashboardPayload) -> dict[str, object]:
    """Testing/production serialization that retains every uncertainty field."""

    return asdict(payload)
