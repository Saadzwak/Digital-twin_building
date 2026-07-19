"""Streamlit rendering for the constrained Pleiades evidence dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from .constrained_chat import answer
from .dashboard_contract import IntervalEstimate, load_dashboard_payload, require_dashboard_access
from .validation_gate import M4ValidationError


def _shown_number(value: float, unit: str) -> str:
    """BIC is intentionally one-decimal in the UI; raw values remain journaled."""

    return f"{value:.1f}" if unit == "BIC" else f"{value:.4g}"


def estimate_table(estimates: tuple[IntervalEstimate, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Valeur": _shown_number(item.value, item.unit),
                "Borne basse": _shown_number(item.lower, item.unit),
                "Borne haute": _shown_number(item.upper, item.unit),
                "Unité": item.unit,
                "Période": item.period,
                "Méthode": item.method,
                "Source": item.run_source,
            }
            for item in estimates
        ]
    )


def basin_table(rows: tuple[dict[str, object], ...]) -> pd.DataFrame:
    """Show all labels, including duplicates, as empirical ranges rather than scores."""

    output = []
    for row in rows:
        q05, q95 = row.get("train_mse_q05"), row.get("train_mse_q95")
        b05, b95 = row.get("validation_bic_q05"), row.get("validation_bic_q95")
        n = int(row["n_starts"])
        near = row.get("near_best_train_fraction")
        output.append(
            {
                "Structure": row["model"],
                "Fini / départs": f"{row['n_finite_train_runs']} / {n}",
                "MSE train q05–q95": "n/a" if q05 is None else f"{float(q05):.5g} – {float(q95):.5g}",
                "BIC validation q05–q95": "n/a" if b05 is None else f"{float(b05):.1f} – {float(b95):.1f}",
                "Près du meilleur / départs": "n/a" if near is None else f"{round(float(near) * n)} / {n}",
                "Confiance d’identification": row["identification_confidence"],
                "Motif": row["confidence_reason"],
            }
        )
    return pd.DataFrame(output)


def render(project_root: Path | str) -> None:
    root = Path(project_root).resolve()
    st.set_page_config(page_title="Pleiades thermal evidence", layout="wide")
    st.title("Pleiades — preuves thermiques, pas de fausse précision")
    try:
        require_dashboard_access(root)
        payload = load_dashboard_payload(root)
    except (M4ValidationError, FileNotFoundError, ValueError) as error:
        st.error("Le tableau de bord est bloqué : aucun artefact M4/M9 validé ne peut être affiché.")
        st.code(str(error))
        st.caption("Aucun chiffre de modèle n’est affiché avant la validation machine du protocole multi-start.")
        st.stop()

    st.caption(f"Source de run : {payload.run_source}")
    if payload.initialization_sensitive:
        st.error(
            "Identification sensible à l’initialisation — les plages inter-départs sont affichées. "
            "Elles décrivent une dispersion empirique, pas des intervalles de confiance statistiques."
        )
    else:
        st.info(payload.initialization_note)

    st.header("Identité thermique")
    st.write(f"Structure retenue : `{payload.topology_label}`")
    st.caption(payload.convergence_status)
    st.info(payload.identity_limit)
    if payload.identity_metrics:
        st.dataframe(estimate_table(payload.identity_metrics), width="stretch", hide_index=True)

    st.header("Dispersion des bassins d’initialisation")
    st.caption(payload.initialization_note)
    st.dataframe(basin_table(tuple(payload.basin_dispersion)), width="stretch", hide_index=True)

    st.header("Répartition des pertes effectives")
    st.caption("Branches extérieures effectives du modèle : elles ne sont pas des pertes par paroi identifiées séparément.")
    st.dataframe(estimate_table(payload.effective_path_losses), width="stretch", hide_index=True)

    st.header("Dérive datée du résidu")
    if payload.dated_drift:
        st.dataframe(estimate_table(payload.dated_drift), width="stretch", hide_index=True)
    else:
        st.info("Aucune rupture datée ne franchit le seuil du détecteur sur validation/test ; ce n’est pas une preuve d’absence de dérive.")

    st.header("Contrefactuels thermiques conditionnels")
    st.caption("Ces scénarios modifient les forçages du modèle pendant le test ; ils ne prédisent ni économie ni effet causal d’une intervention réelle.")
    st.dataframe(estimate_table(payload.conditional_counterfactuals), width="stretch", hide_index=True)

    st.header("Classement des scénarios")
    st.caption("Classement par amplitude thermique simulée, pas une recommandation de travaux.")
    st.dataframe(estimate_table(payload.intervention_ranking), width="stretch", hide_index=True)

    st.header("Plans et questions d’onboarding")
    st.write(f"Géométrie : `{payload.geometry_status}`")
    st.caption(payload.onboarding_status)
    onboarding_path = root / "runs" / "m8" / "onboarding_contract.json"
    if onboarding_path.is_file():
        onboarding = json.loads(onboarding_path.read_text(encoding="utf-8"))
        questions = onboarding.get("questions", [])
        if questions:
            for number, question in enumerate(questions, start=1):
                st.write(f"{number}. {question['prompt']}")
                st.caption(question["why_needed"])
        else:
            st.caption("Aucune question non résolue dans le contrat courant.")
    else:
        st.caption("Contrat d’onboarding absent.")
    if payload.duplicate_labels:
        st.caption("Labels dupliqués conservés dans le protocole : " + ", ".join(payload.duplicate_labels))

    st.header("Chat contraint aux paramètres identifiés")
    query = st.text_input("Question", placeholder="Ex. Quel est le RMSE de validation ?")
    if st.button("Répondre", type="primary"):
        if not query.strip():
            st.warning("Saisissez une question dans le périmètre affiché.")
        else:
            card = answer(query, root)
            if card.kind == "answer":
                st.success(card.text)
                if card.estimates:
                    st.dataframe(estimate_table(card.estimates), width="stretch", hide_index=True)
            elif card.kind == "blocked":
                st.error(card.text)
            else:
                st.warning(card.text)
            if card.scope_note:
                st.caption(card.scope_note)
