"""Read-only, integrity-checked access to a validated multi-start M4 run."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .identification import FittedTopology
from .reference_ingestion import split_reference_months
from .topologies import reference_model_bank
from .validation_gate import M4ValidationError, require_validated_m4


@dataclass(frozen=True)
class SelectedM4Fit:
    run_source: str
    validation_route: str
    topology_label: str
    topology_index: int
    selected_start_id: int
    fitted: FittedTopology
    selected_row: dict[str, object]
    outcome_row: dict[str, object]
    all_outcomes_for_topology: tuple[dict[str, object], ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_integrity(verdict: dict[str, object], payload: dict[str, object], path: Path) -> None:
    integrity = verdict.get("artifact_integrity")
    if not isinstance(integrity, dict):
        raise M4ValidationError("Validated M4 verdict lacks a sealed all-starts artifact record.")
    if integrity.get("all_starts_sha256") != _sha256(path):
        raise M4ValidationError("all_starts.json hash does not match the validated M4 verdict.")
    if payload.get("config") != verdict.get("config") or payload.get("config") != integrity.get("config"):
        raise M4ValidationError("M4 all-starts configuration does not match its validated verdict.")
    outcomes = payload.get("outcomes")
    if not isinstance(outcomes, list):
        raise M4ValidationError("M4 all-starts artifact has no outcome list.")
    pairs = {(row.get("model_index"), row.get("start_id")) for row in outcomes if isinstance(row, dict)}
    if integrity.get("outcome_count") != len(outcomes) or integrity.get("unique_model_start_pairs") != len(pairs):
        raise M4ValidationError("M4 all-starts coverage no longer matches the validated verdict.")


def load_hourly_splits(project_root: Path | str) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    root = Path(project_root).resolve()
    path = root / "data" / "processed" / "hourly_reference.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Processed reference data is absent: {path}")
    hourly = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")
    return hourly, split_reference_months(hourly)


def load_selected_m4_fit(project_root: Path | str) -> SelectedM4Fit:
    """Reconstruct only the train-selected start of the BIC-ranked topology."""

    root = Path(project_root).resolve()
    verdict = require_validated_m4(root)
    path = root / "runs" / "m4" / "multistart" / "all_starts.json"
    if not path.is_file():
        raise FileNotFoundError(f"Validated multi-start attempts are absent: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise M4ValidationError("M4 all-starts artifact must be a JSON object.")
    _require_integrity(verdict, payload, path)
    selected = payload.get("selected")
    outcomes = payload.get("outcomes")
    if not isinstance(selected, list) or not isinstance(outcomes, list) or len(selected) != 19:
        raise M4ValidationError("Validated M4 artifacts have no complete selected/start record.")
    selected_row = min(selected, key=lambda row: float(row["validation_bic"]))
    index = int(selected_row["model_index"])
    start_id = int(selected_row["selected_start_id"])
    outcome = next(
        (row for row in outcomes if int(row["model_index"]) == index and int(row["start_id"]) == start_id),
        None,
    )
    if outcome is None or outcome.get("final_parameters_log") is None:
        raise M4ValidationError("Selected M4 start has no final parameter vector.")
    bank = reference_model_bank()
    topology = bank[index]
    if topology.name != selected_row["model"] or topology.name != outcome["model"]:
        raise M4ValidationError("Selected M4 topology label no longer matches the frozen bank.")
    theta = np.asarray(outcome["final_parameters_log"], dtype=float)
    physical = np.exp(theta)
    fitted = FittedTopology(
        topology=topology,
        parameters_log=theta,
        resistances=physical[: topology.n_resistances],
        capacitances=physical[topology.n_resistances : topology.n_resistances + topology.n_capacitances],
        alpha=float(physical[-1]),
        n_parameters=topology.n_resistances + topology.n_capacitances + 1,
        success=bool(outcome["fit_success"]),
        status=int(outcome["fit_status"]) if outcome["fit_status"] is not None else -1,
        message=str(outcome["fit_message"]),
        nfev=int(outcome["nfev"]) if outcome["nfev"] is not None else None,
        nit=int(outcome["nit"]) if outcome["nit"] is not None else None,
        objective_mse=float(outcome["train_mse"]),
    )
    same_topology = tuple(row for row in outcomes if int(row["model_index"]) == index)
    return SelectedM4Fit(
        run_source=f"m4-multistart-{_sha256(path)[:16]}",
        validation_route=str(verdict.get("validation_route", verdict.get("verdict", "UNKNOWN"))),
        topology_label=topology.name,
        topology_index=index,
        selected_start_id=start_id,
        fitted=fitted,
        selected_row=dict(selected_row),
        outcome_row=dict(outcome),
        all_outcomes_for_topology=same_topology,
    )
