"""Local evidence dashboard: M4/M5/M9/M10 artifacts only."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import streamlit as st

from thermal_twin.constrained_chat import answer
from thermal_twin.dashboard_contract import IntervalEstimate, load_dashboard_payload, require_dashboard_access
from thermal_twin.validation_gate import M4ValidationError


ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="Pleiades thermal evidence", layout="wide")
st.title("Pleiades — preuves thermiques, pas de fausse précision")


def estimate_table(estimates: tuple[IntervalEstimate, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Valeur": item.value,
                "Borne basse": item.lower,
                "Borne haute": item.upper,
                "Unité": item.unit,
                "Période": item.period,
                "Méthode": item.method,
                "Source": item.run_source,
            }
            for item in estimates
        ]
    )


try:
    require_dashboard_access(ROOT)
    payload = load_dashboard_payload(ROOT)
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
    st.dataframe(estimate_table(payload.identity_metrics), use_container_width=True, hide_index=True)

st.header("Dispersion des bassins d’initialisation")
st.caption(payload.initialization_note)
if payload.basin_dispersion:
    st.json(payload.basin_dispersion[0], expanded=False)
else:
    st.info("Aucun résumé de dispersion n’est disponible.")

st.header("Répartition des pertes effectives")
st.caption("Branches extérieures effectives du modèle : elles ne sont pas des pertes par paroi identifiées séparément.")
st.dataframe(estimate_table(payload.effective_path_losses), use_container_width=True, hide_index=True)

st.header("Dérive datée du résidu")
if payload.dated_drift:
    st.dataframe(estimate_table(payload.dated_drift), use_container_width=True, hide_index=True)
else:
    st.info("Aucune rupture datée ne franchit le seuil du détecteur sur validation/test ; ce n’est pas une preuve d’absence de dérive.")

st.header("Contrefactuels thermiques conditionnels")
st.caption("Ces scénarios modifient les forçages du modèle pendant le test ; ils ne prédisent ni économie ni effet causal d’une intervention réelle.")
st.dataframe(estimate_table(payload.conditional_counterfactuals), use_container_width=True, hide_index=True)

st.header("Classement des scénarios")
st.caption("Classement par amplitude thermique simulée, pas une recommandation de travaux.")
st.dataframe(estimate_table(payload.intervention_ranking), use_container_width=True, hide_index=True)

st.header("Plans et questions d’onboarding")
st.write(f"Géométrie : `{payload.geometry_status}`")
st.caption(payload.onboarding_status)
onboarding_path = ROOT / "runs" / "m8" / "onboarding_contract.json"
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
        card = answer(query, ROOT)
        if card.kind == "answer":
            st.success(card.text)
            if card.estimates:
                st.dataframe(estimate_table(card.estimates), use_container_width=True, hide_index=True)
        elif card.kind == "blocked":
            st.error(card.text)
        else:
            st.warning(card.text)
        if card.scope_note:
            st.caption(card.scope_note)
