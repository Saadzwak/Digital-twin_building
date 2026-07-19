"""Local Streamlit dashboard constrained to a validated M4 artifact."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st

from thermal_twin.dashboard_contract import load_dashboard_payload, require_dashboard_access
from thermal_twin.validation_gate import M4ValidationError


ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="Pleiades thermal evidence", layout="wide")
st.title("Thermal evidence, not false precision")

try:
    require_dashboard_access(ROOT)
except M4ValidationError as error:
    st.error("Identity, losses, drift and interventions are blocked: M4 reproduction is not validated.")
    st.code(str(error))
    st.caption("See runs/m4/diagnostic_comparatif.md. No model-derived number is shown here.")
    st.stop()

payload = load_dashboard_payload(ROOT)
st.caption(f"Validated run source: {payload.run_source}")
st.subheader("Thermal identity")
st.write(payload.topology_label)
st.caption(f"Convergence: {payload.convergence_status}. {payload.identity_limit}")


def show_estimates(title: str, estimates: tuple) -> None:
    st.subheader(title)
    for estimate in estimates:
        st.write(
            f"{estimate.value:.3g} {estimate.unit} "
            f"[{estimate.lower:.3g}, {estimate.upper:.3g}] — {estimate.period}; "
            f"{estimate.method}; source {estimate.run_source}"
        )


show_estimates("Effective thermal paths (not individual walls)", payload.effective_path_losses)
show_estimates("Dated residual drift", payload.dated_drift)
show_estimates("Conditional thermal counterfactuals", payload.conditional_counterfactuals)
show_estimates("Intervention ranking", payload.intervention_ranking)
if payload.duplicate_labels:
    st.caption("Retained duplicate labels: " + ", ".join(payload.duplicate_labels))
