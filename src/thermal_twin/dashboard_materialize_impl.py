"""Create a constrained M9 payload from executed M4/M5 artifacts only."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .dashboard_contract import DashboardPayload, IntervalEstimate, serialize_payload
from .m4_artifacts import load_hourly_splits, load_selected_m4_fit
from .rc_core import simulate_open_loop
from .topologies import reference_model_bank
from .validation_gate import initialization_sensitive, require_validated_m4


def _bounded(value: float, lower: float, upper: float) -> tuple[float, float]:
    """Retain a displayed selected value inside its empirical interval."""

    return min(float(value), float(lower)), max(float(value), float(upper))


def _empirical_estimate(
    value: float,
    values: list[float],
    unit: str,
    period: str,
    method: str,
    run_source: str,
) -> IntervalEstimate:
    if not values:
        raise ValueError("A dashboard estimate requires at least one sampled result.")
    lower, upper = _bounded(value, np.quantile(values, 0.05), np.quantile(values, 0.95))
    return IntervalEstimate(
        value=float(value), lower=lower, upper=upper, unit=unit, period=period,
        method=method + "; empirical q05–q95 expanded to include the train-selected start",
        run_source=run_source,
    )


def _bootstrap_estimate(
    interval: dict[str, object],
    unit: str,
    period: str,
    method: str,
    run_source: str,
) -> IntervalEstimate:
    value = float(interval["estimate"])
    lower, upper = _bounded(value, float(interval["lower"]), float(interval["upper"]))
    return IntervalEstimate(value, lower, upper, unit, period, method, run_source)


def _m5_payload(root: Path) -> dict[str, object]:
    path = root / "runs" / "m5" / "diagnostic.json"
    if not path.is_file():
        raise FileNotFoundError("M5 diagnostics are absent; M9 cannot invent a dashboard payload.")
    return json.loads(path.read_text(encoding="utf-8"))


def _scenario_effects(selected, test) -> tuple[IntervalEstimate, ...]:
    params = [
        np.asarray(row["final_parameters_log"], dtype=float)
        for row in selected.all_outcomes_for_topology
        if row.get("final_parameters_log") is not None
    ]
    if not params:
        raise ValueError("No terminal parameter vectors are available for conditional scenarios.")
    tout = test["Tout"].to_numpy(dtype=float)
    q = test["Qhvac_W_A"].to_numpy(dtype=float)
    tin0 = float(test["Tin"].iloc[0])

    def effect(theta: np.ndarray, scenario: str) -> float:
        baseline = simulate_open_loop(selected.fitted.topology, tout, q, 3600.0, theta, tin0)
        if scenario == "q_plus_10pct":
            alternative = simulate_open_loop(selected.fitted.topology, tout, q * 1.10, 3600.0, theta, tin0)
        elif scenario == "tout_plus_1c":
            alternative = simulate_open_loop(selected.fitted.topology, tout + 1.0, q, 3600.0, theta, tin0)
        else:
            raise ValueError(scenario)
        return float(np.mean(alternative[1:] - baseline[1:]))

    scenarios = (
        ("+10 % du signal Q HVAC", "q_plus_10pct"),
        ("+1 °C du forçage extérieur", "tout_plus_1c"),
    )
    result = []
    for label, scenario in scenarios:
        values = [effect(theta, scenario) for theta in params]
        selected_value = effect(selected.fitted.parameters_log, scenario)
        result.append(
            _empirical_estimate(
                selected_value,
                values,
                "°C de Tin moyen",
                "test (680 h), conditionnel aux entrées observées",
                f"contre-factuel RC : {label}; pas une économie ni une causalité d’intervention",
                selected.run_source,
            )
        )
    return tuple(result)


def materialize_dashboard_payload(project_root: Path | str) -> DashboardPayload:
    """Build M9 after M5, never from fabricated geometry or intervention data."""

    root = Path(project_root).resolve()
    verdict = require_validated_m4(root)
    selected = load_selected_m4_fit(root)
    _, splits = load_hourly_splits(root)
    m5 = _m5_payload(root)
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
                f"conductance effective de la branche extérieure R{resistance_index}; nœud {selected.fitted.topology.node_names[node]}; non assimilable à une paroi",
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
            "BIC", "validation (1464 h)",
            "BIC du départ retenu par MSE train", selected.run_source,
        ),
    )
    drift = []
    for split_name in ("validation", "test"):
        for item in m5["regime_breaks"].get(split_name, [])[:3]:
            value = float(item["median_shift_c"])
            scale = float(item["robust_scale_c"])
            drift.append(
                IntervalEstimate(
                    value=value,
                    lower=value - scale,
                    upper=value + scale,
                    unit="°C de résidu",
                    period=f"{split_name}, {item['timestamp']}",
                    method="rupture locale 24 h; enveloppe ±MAD locale (échelle diagnostique, pas IC)",
                    run_source=selected.run_source,
                )
            )
    scenarios = _scenario_effects(selected, splits["test"])
    ranked = tuple(sorted(scenarios, key=lambda estimate: abs(estimate.value), reverse=True))
    duplicate_labels = tuple(item.name for item in reference_model_bank() if item.duplicate_of is not None)
    geometry_path = root / "runs" / "m6" / "geometry_review_request.json"
    geometry_status = "HUMAN_VALIDATION_REQUIRED"
    if geometry_path.is_file():
        geometry_status = str(json.loads(geometry_path.read_text(encoding="utf-8")).get("status", geometry_status))
    sensitive = initialization_sensitive(verdict)
    payload = DashboardPayload(
        run_source=selected.run_source,
        topology_label=selected.topology_label,
        convergence_status=(
            f"optimizer success={selected.fitted.success}, status={selected.fitted.status}; "
            f"selected start={selected.selected_start_id} by minimum train MSE"
        ),
        identity_limit="Les états et branches RC sont effectifs : aucune capacité ni perte par paroi indépendante n’est identifiée.",
        effective_path_losses=tuple(effective_paths),
        dated_drift=tuple(drift),
        conditional_counterfactuals=scenarios,
        intervention_ranking=ranked,
        duplicate_labels=duplicate_labels,
        identity_metrics=identity_metrics,
        initialization_sensitive=sensitive,
        initialization_note=(
            "Identification sensible à l’initialisation : les plages inter-départs sont affichées et ne sont pas des IC statistiques."
            if sensitive
            else "La banque de départs échantillonnée est stable selon le critère défini; ce n’est pas une garantie d’unicité globale."
        ),
        basin_dispersion=tuple(m5["initialization_sensitivity"] for _ in [0]),
        geometry_status=geometry_status,
        onboarding_status="Questions M8 disponibles; aucune géométrie non validée ne nourrit le modèle.",
    )
    directory = root / "runs" / "m9"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "dashboard_payload.json").write_text(
        json.dumps(serialize_payload(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload
