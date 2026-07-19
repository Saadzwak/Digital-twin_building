"""M4 non-regression runner and explicit comparison against notebook cell 55."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import pandas as pd

from .identification import Evaluation, FittedTopology, evaluate_topology, fit_to_serializable, fit_topology
from .reference_ingestion import split_reference_months
from .topologies import reference_model_bank


@dataclass(frozen=True)
class NotebookReference:
    validation_rmse: float
    validation_bic: float
    test_rmse: float
    success: bool


# Raw reference values transcribed from the executed output of notebook cell 55.
NOTEBOOK_REFERENCE: dict[str, NotebookReference] = {
    "LADDER_1R1C": NotebookReference(5.006645, 4738.189891, 0.849438, True),
    "LADDER_2R2C": NotebookReference(5.006811, 4752.864770, 0.849500, False),
    "LADDER_3R3C": NotebookReference(5.006419, 4767.213098, 0.849068, True),
    "LADDER_4R4C": NotebookReference(5.006899, 4782.071618, 0.849477, True),
    "LADDER_5R5C": NotebookReference(5.006922, 4796.663186, 0.849496, True),
    "LADDER_6R6C": NotebookReference(5.006929, 4811.245026, 0.849502, True),
    "LADDER_7R7C": NotebookReference(5.006941, 4825.829766, 0.849512, True),
    "LADDER_8R8C": NotebookReference(5.006925, 4840.398288, 0.849498, True),
    "LADDER_9R9C": NotebookReference(5.006949, 4854.990524, 0.849521, True),
    "LADDER_10R10C": NotebookReference(5.006735, 4869.442915, 0.849339, True),
    "STD_1R1C": NotebookReference(5.006645, 4738.189891, 0.849438, True),
    "STD_2R1C_parallel_losses": NotebookReference(5.006727, 4745.526725, 0.849499, True),
    "STD_2R2C_air_mass": NotebookReference(5.006811, 4752.864770, 0.849500, False),
    "STD_3R2C_air_shunt": NotebookReference(4.975361, 4741.703687, 0.851451, True),
    "STD_3R3C_two_masses_series": NotebookReference(5.006419, 4767.213098, 0.849068, True),
    "STD_4R3C_two_masses_plus_air_shunt": NotebookReference(4.682382, 4578.578337, 0.857599, True),
    "STD_5R3C_air_shunt_mid_shunt": NotebookReference(5.006278, 4781.708599, 0.874338, True),
    "STD_6R4C_three_masses_plus_shunts": NotebookReference(5.022779, 4805.921252, 0.902459, True),
    "STD_7R5C_four_masses_plus_shunts": NotebookReference(5.007632, 4811.656407, 0.850929, True),
}


@dataclass(frozen=True)
class ReproductionRow:
    model: str
    n_nodes: int
    n_resistances: int
    n_capacitances: int
    n_parameters: int
    duplicate_of: str | None
    fit_success: bool
    fit_status: int
    fit_message: str
    fit_nfev: int | None
    validation_rmse: float
    validation_mae: float
    validation_bic: float
    test_rmse: float
    test_mae: float
    expected_validation_rmse: float
    expected_validation_bic: float
    expected_test_rmse: float
    expected_success: bool
    delta_validation_rmse: float
    delta_validation_bic: float
    delta_test_rmse: float


def run_reproduction(hourly: pd.DataFrame) -> tuple[list[ReproductionRow], dict[str, FittedTopology], dict[str, Evaluation]]:
    """Fit all 19 labels in fixed order; no label or unsuccessful fit is dropped."""

    splits = split_reference_months(hourly)
    rows: list[ReproductionRow] = []
    fits: dict[str, FittedTopology] = {}
    validations: dict[str, Evaluation] = {}
    for topology in reference_model_bank():
        fitted = fit_topology(topology, splits["train"])
        validation = evaluate_topology(fitted, splits["validation"])
        testing = evaluate_topology(fitted, splits["test"])
        reference = NOTEBOOK_REFERENCE[topology.name]
        rows.append(
            ReproductionRow(
                model=topology.name,
                n_nodes=topology.n_nodes,
                n_resistances=topology.n_resistances,
                n_capacitances=topology.n_capacitances,
                n_parameters=fitted.n_parameters,
                duplicate_of=topology.duplicate_of,
                fit_success=fitted.success,
                fit_status=fitted.status,
                fit_message=fitted.message,
                fit_nfev=fitted.nfev,
                validation_rmse=validation.metrics.rmse,
                validation_mae=validation.metrics.mae,
                validation_bic=validation.metrics.bic,
                test_rmse=testing.metrics.rmse,
                test_mae=testing.metrics.mae,
                expected_validation_rmse=reference.validation_rmse,
                expected_validation_bic=reference.validation_bic,
                expected_test_rmse=reference.test_rmse,
                expected_success=reference.success,
                delta_validation_rmse=validation.metrics.rmse - reference.validation_rmse,
                delta_validation_bic=validation.metrics.bic - reference.validation_bic,
                delta_test_rmse=testing.metrics.rmse - reference.test_rmse,
            )
        )
        fits[topology.name] = fitted
        validations[topology.name] = validation
    return rows, fits, validations


def primary_validation(rows: list[ReproductionRow], tolerance: float = 1e-6) -> dict[str, object]:
    """Evaluate the user's immutable M4 acceptance criteria without masking deltas."""

    if len(rows) != 19:
        return {"passed": False, "reason": f"Expected 19 model labels, got {len(rows)}."}
    selected = next((row for row in rows if row.model == "STD_4R3C_two_masses_plus_air_shunt"), None)
    if selected is None:
        return {"passed": False, "reason": "STD_4R3C row absent."}
    std4_exact = (
        abs(selected.validation_rmse - 4.682382) <= tolerance
        and abs(selected.validation_bic - 4578.578337) <= tolerance
        and abs(selected.test_rmse - 0.857599) <= tolerance
    )
    others = [row for row in rows if row.model != selected.model]
    eighteen_in_range = sum(4.98 <= row.validation_rmse <= 5.02 for row in others)
    return {
        "passed": bool(std4_exact and eighteen_in_range == 18),
        "tolerance": tolerance,
        "std_4r3c_exact": std4_exact,
        "eighteen_in_4_98_5_02": eighteen_in_range,
        "std_4r3c": {
            "validation_rmse": selected.validation_rmse,
            "validation_bic": selected.validation_bic,
            "test_rmse": selected.test_rmse,
        },
    }


def write_reproduction_artifacts(
    project_root: Path | str,
    rows: list[ReproductionRow],
    fits: dict[str, FittedTopology],
    validation: dict[str, Evaluation],
) -> tuple[Path, Path]:
    """Journalise valeurs brutes, statuts, doublons et verdict sans les arrondir."""

    root = Path(project_root).resolve()
    run_dir = root / "runs" / "m4"
    run_dir.mkdir(parents=True, exist_ok=True)
    csv_path = run_dir / "reproduction_19_models.csv"
    json_path = run_dir / "reproduction_19_models.json"
    pd.DataFrame([asdict(row) for row in rows]).to_csv(csv_path, index=False)
    payload = {
        "protocol": "notebook_cell_55_reference",
        "residual_convention": "Tin_measured - Tin_estimated",
        "rows": [asdict(row) for row in rows],
        "fits": {name: fit_to_serializable(fitted) for name, fitted in fits.items()},
        "primary_validation": primary_validation(rows),
        "display_rounding": {"rmse_decimals": 2, "bic_decimals": 1},
        "duplicates_retained": [
            {"model": row.model, "duplicate_of": row.duplicate_of}
            for row in rows
            if row.duplicate_of is not None
        ],
        "validation_residual_available_for": sorted(validation),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return csv_path, json_path
