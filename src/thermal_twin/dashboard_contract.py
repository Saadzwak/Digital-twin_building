"""Strict M9 contract: sourced intervals and a complete M4 dispersion bank."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Mapping

from .validation_gate import M4ValidationError, require_validated_m4


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


_BASIN_FIELDS = {
    "model", "model_index", "n_starts", "n_finite_train_runs", "train_mse_q05", "train_mse_q95",
    "validation_bic_q05", "validation_bic_q95", "identification_confidence", "confidence_reason",
}


@dataclass(frozen=True)
class DashboardPayload:
    run_source: str
    topology_label: str
    convergence_status: str
    identity_limit: str
    effective_path_losses: tuple[IntervalEstimate, ...]
    dated_drift: tuple[IntervalEstimate, ...]
    conditional_counterfactuals: tuple[IntervalEstimate, ...]
    intervention_ranking: tuple[IntervalEstimate, ...]
    duplicate_labels: tuple[str, ...]
    identity_metrics: tuple[IntervalEstimate, ...] = ()
    initialization_sensitive: bool = False
    initialization_note: str = ""
    basin_dispersion: tuple[Mapping[str, object], ...] = ()
    geometry_status: str = "HUMAN_VALIDATION_REQUIRED"
    onboarding_status: str = ""

    def __post_init__(self) -> None:
        forbidden = ("wall", "façade", "facade", "paroi")
        for estimate in self.effective_path_losses:
            if any(word in estimate.method.lower() for word in forbidden):
                raise ValueError("Effective paths must not be relabeled as independently identified walls.")
        if self.initialization_sensitive and not self.initialization_note:
            raise ValueError("Initialization-sensitive runs require a permanent visible caveat.")
        for group in (self.identity_metrics, self.effective_path_losses, self.dated_drift, self.conditional_counterfactuals, self.intervention_ranking):
            for estimate in group:
                if not isinstance(estimate, IntervalEstimate):
                    raise ValueError("Every numeric dashboard item must be an IntervalEstimate.")
        if self.basin_dispersion:
            if len(self.basin_dispersion) != 19:
                raise ValueError("Dashboard requires a dispersion row for every one of the 19 fixed labels.")
            indices = set()
            for row in self.basin_dispersion:
                if not _BASIN_FIELDS.issubset(row):
                    raise ValueError("A basin dispersion row is missing required provenance/uncertainty fields.")
                index = int(row["model_index"])
                if index in indices or not 0 <= index < 19:
                    raise ValueError("Basin dispersion must use each fixed model index exactly once.")
                indices.add(index)
                if int(row["n_starts"]) < 2 or not 0 <= int(row["n_finite_train_runs"]) <= int(row["n_starts"]):
                    raise ValueError("Basin dispersion start counts are invalid.")
                for lower_key, upper_key in (("train_mse_q05", "train_mse_q95"), ("validation_bic_q05", "validation_bic_q95")):
                    lower, upper = row[lower_key], row[upper_key]
                    if lower is not None and upper is not None and float(lower) > float(upper):
                        raise ValueError("Basin empirical q05 cannot exceed q95.")


def require_dashboard_access(project_root: Path | str) -> dict[str, object]:
    return require_validated_m4(project_root)


def load_dashboard_payload(project_root: Path | str) -> DashboardPayload:
    root = Path(project_root).resolve()
    require_dashboard_access(root)
    path = root / "runs" / "m9" / "dashboard_payload.json"
    if not path.is_file():
        raise FileNotFoundError(f"Validated dashboard payload is absent: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    # Bind the product payload to the current sealed M4 all-starts artifact.
    from .m4_artifacts import load_selected_m4_fit

    selected = load_selected_m4_fit(root)
    if raw.get("run_source") != selected.run_source:
        raise M4ValidationError("Dashboard payload run source does not match the sealed validated M4 artifact.")
    to_estimate = lambda values: tuple(IntervalEstimate(**value) for value in values)
    return DashboardPayload(
        run_source=raw["run_source"], topology_label=raw["topology_label"], convergence_status=raw["convergence_status"],
        identity_limit=raw["identity_limit"], effective_path_losses=to_estimate(raw["effective_path_losses"]),
        dated_drift=to_estimate(raw["dated_drift"]), conditional_counterfactuals=to_estimate(raw["conditional_counterfactuals"]),
        intervention_ranking=to_estimate(raw["intervention_ranking"]), duplicate_labels=tuple(raw["duplicate_labels"]),
        identity_metrics=to_estimate(raw.get("identity_metrics", [])), initialization_sensitive=bool(raw.get("initialization_sensitive", False)),
        initialization_note=str(raw.get("initialization_note", "")), basin_dispersion=tuple(raw.get("basin_dispersion", [])),
        geometry_status=str(raw.get("geometry_status", "HUMAN_VALIDATION_REQUIRED")), onboarding_status=str(raw.get("onboarding_status", "")),
    )


def serialize_payload(payload: DashboardPayload) -> dict[str, object]:
    return asdict(payload)
