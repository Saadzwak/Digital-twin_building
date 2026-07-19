"""Atomic M9 materialization from integrity-checked M4/M5 artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .dashboard_contract import DashboardPayload, IntervalEstimate, serialize_payload
from .dashboard_materialize_impl import _bootstrap_estimate, _empirical_estimate, _m5_payload, _scenario_effects
from .m4_artifacts import load_hourly_splits, load_selected_m4_fit
from .topologies import reference_model_bank
from .validation_gate import M4ValidationError, initialization_sensitive, require_validated_m4


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_reread_all_starts(verdict: dict[str, object], path: Path, payload: object) -> dict[str, object]:
    """Reject a concurrent/new M4 artifact before using its dispersion rows."""

    if not isinstance(payload, dict):
        raise M4ValidationError("M4 all-starts artifact must be a JSON object.")
    integrity = verdict.get("artifact_integrity")
    if not isinstance(integrity, dict) or integrity.get("all_starts_sha256") != _sha256(path):
        raise M4ValidationError("M4 all-starts changed after the selected fit was integrity-checked.")
    if payload.get("config") != verdict.get("config"):
        raise M4ValidationError("Re-read M4 all-starts configuration does not match the validated verdict.")
    return payload


def materialize_dashboard_payload(project_root: Path | str) -> DashboardPayload:
    """Create and atomically publish one schema-valid full-bank dashboard payload."""

    root = Path(project_root).resolve()
    verdict = require_validated_m4(root)
    selected = load_selected_m4_fit(root)  # validates all-starts hash/coverage
    _, splits = load_hourly_splits(root)
    m5 = _m5_payload(root)
    if m5.get("run_source") != selected.run_source:
        raise M4ValidationError("M5 diagnostic run source does not match the sealed selected M4 artifact.")
    all_starts_path = root / "runs" / "m4" / "multistart" / "all_starts.json"
    all_starts = _verify_reread_all_starts(
        verdict, all_starts_path, json.loads(all_starts_path.read_text(encoding="utf-8"))
    )
    summaries = tuple(sorted(all_starts["basin_summaries"], key=lambda row: int(row["model_index"])))
    if len(summaries) != 19:
        raise ValueError("M9 requires a dispersion summary for every fixed M4 label.")
    parameters = [
        np.exp(np.asarray(row["final_parameters_log"], dtype=float))
        for row in selected.all_outcomes_for_topology
        if row.get("final_parameters_log") is not None
    ]
    effective_paths = []
    for node, resistance_index in selected.fitted.topology.outdoor_edges:
        values = [float(1.0 / vector[resistance_index]) for vector in parameters]
        effective_paths.append(
            _empirical_estimate(
                float(1.0 / selected.fitted.resistances[resistance_index]),
                values,
                "W/K",
                "paramètres identifiés sur train (6460 h)",
                f"conductance effective de la branche extérieure R{resistance_index}; nœud {selected.fitted.topology.node_names[node]}; sans interprétation par élément d’enveloppe indépendant",
                selected.run_source,
            )
        )
    validation_metrics = m5["metrics"]["validation"]
    identity_metrics = (
        _bootstrap_estimate(
            validation_metrics["residual_rmse_c"], "°C", "validation (1464 h)",
            "RMSE des résidus, bootstrap par blocs 24 h / 300 réplications", selected.run_source,
        ),
        _empirical_estimate(
            float(selected.selected_row["validation_bic"]),
            [float(row["validation_bic"]) for row in selected.all_outcomes_for_topology if row.get("validation_bic") is not None],
            "BIC", "validation (1464 h)", "BIC du départ retenu par MSE train", selected.run_source,
        ),
    )
    drift = []
    for split_name in ("validation", "test"):
        for item in m5["regime_breaks"].get(split_name, [])[:3]:
            value = float(item["median_shift_c"])
            scale = float(item["robust_scale_c"])
            drift.append(
                IntervalEstimate(
                    value=value, lower=value - scale, upper=value + scale,
                    unit="°C de résidu", period=f"{split_name}, {item['timestamp']}",
                    method="rupture locale 24 h; enveloppe ±MAD locale (échelle diagnostique, pas IC)",
                    run_source=selected.run_source,
                )
            )
    scenarios = _scenario_effects(selected, splits["test"])
    duplicate_labels = tuple(item.name for item in reference_model_bank() if item.duplicate_of is not None)
    geometry_path = root / "runs" / "m6" / "geometry_review_request.json"
    geometry_status = "HUMAN_VALIDATION_REQUIRED"
    if geometry_path.is_file():
        geometry_status = str(json.loads(geometry_path.read_text(encoding="utf-8")).get("status", geometry_status))
    sensitive = initialization_sensitive(verdict)
    payload = DashboardPayload(
        run_source=selected.run_source,
        topology_label=selected.topology_label,
        convergence_status=f"optimizer success={selected.fitted.success}, status={selected.fitted.status}; selected start={selected.selected_start_id} by minimum train MSE",
        identity_limit="Les états et branches RC sont effectifs : aucune capacité ni perte par paroi indépendante n’est identifiée.",
        effective_path_losses=tuple(effective_paths),
        dated_drift=tuple(drift),
        conditional_counterfactuals=scenarios,
        intervention_ranking=tuple(sorted(scenarios, key=lambda estimate: abs(estimate.value), reverse=True)),
        duplicate_labels=duplicate_labels,
        identity_metrics=identity_metrics,
        initialization_sensitive=sensitive,
        initialization_note=(
            "Identification sensible à l’initialisation : les plages inter-départs sont affichées et ne sont pas des IC statistiques."
            if sensitive else "La banque de départs échantillonnée est stable selon le critère défini; ce n’est pas une garantie d’unicité globale."
        ),
        basin_dispersion=summaries,
        geometry_status=geometry_status,
        onboarding_status="Questions M8 disponibles; aucune géométrie non validée ne nourrit le modèle.",
    )
    directory = root / "runs" / "m9"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "dashboard_payload.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(serialize_payload(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return payload
