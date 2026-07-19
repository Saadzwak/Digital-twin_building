"""Owner-facing Streamlit product: landing, live execution, dashboard.

Progress shown during execution reflects the real computation stream from
``live_run.run_live_pipeline`` — there is no simulated delay or animation.
Surface wording is business language; the methodological detail keeps the
full technical rigor inside a collapsed section.
"""

from __future__ import annotations

from pathlib import Path
import json
import time

import altair as alt
import pandas as pd
import streamlit as st

from .live_run import (
    DemoConfig,
    load_drift_daily,
    load_product_payload,
    prepare_uploaded_csv,
    run_live_pipeline,
)
from .product_chat import product_answer

STAGE_TITLES = {
    "plans": "Étape 1 — Lecture des plans",
    "data": "Étape 2 — Préparation des données",
    "bank": "Étape 3 — Banc de structures candidates",
    "drift": "Étape 5 — Diagnostic de dérive annuelle",
    "scenarios": "Scénarios d'intervention",
}


def render(project_root: Path | str) -> None:
    root = Path(project_root).resolve()
    st.set_page_config(page_title="Diagnostic thermique Pleiades", layout="wide")
    page = st.session_state.setdefault("page", "accueil")
    if page == "execution":
        _render_execution(root)
    elif page == "tableau":
        _render_dashboard(root)
    else:
        _render_landing(root)


# --------------------------------------------------------------------- landing

def _render_landing(root: Path) -> None:
    st.title("Votre bâtiment, expliqué par ses mesures")
    st.write(
        "Déposez un plan et un an de mesures : la plateforme calibre un jumeau thermique, "
        "montre le calcul en direct, date le moment où le bâtiment change de comportement "
        "et simule des interventions — avec les fourchettes d'incertitude, jamais sans."
    )
    left, right = st.columns(2)
    with left:
        st.subheader("Plan du bâtiment (PDF)")
        plan_files = st.file_uploader(
            "Plans 2D", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed"
        )
        st.caption("Optionnel. Les plans restent soumis à votre validation avant tout usage géométrique.")
    with right:
        st.subheader("Mesures (CSV)")
        csv_file = st.file_uploader(
            "CSV : horodatage, T intérieure, T extérieure, consommation HVAC",
            type=["csv"], label_visibility="collapsed",
        )
        st.caption("Au moins 1000 heures. Colonnes reconnues par leur nom (timestamp, Tin, Tout, HVAC…).")

    if csv_file is not None and st.button("Analyser mes fichiers", type="primary"):
        try:
            hourly, provenance = prepare_uploaded_csv(csv_file.getvalue())
        except ValueError as error:
            st.error(str(error))
        else:
            plan_paths: list[Path] = []
            if plan_files:
                upload_dir = root / "runs" / "demo" / "uploads"
                upload_dir.mkdir(parents=True, exist_ok=True)
                for uploaded in plan_files:
                    path = upload_dir / uploaded.name
                    path.write_bytes(uploaded.getvalue())
                    plan_paths.append(path)
            st.session_state["upload"] = {
                "hourly": hourly, "provenance": provenance, "plan_paths": tuple(plan_paths),
            }
            st.session_state["run_pending"] = True
            st.session_state["page"] = "execution"
            st.rerun()

    st.divider()
    st.subheader("Ou essayez immédiatement")
    if st.button("Essayer avec le bâtiment Pleiades", type="primary"):
        st.session_state["upload"] = None
        st.session_state["run_pending"] = True
        st.session_state["page"] = "execution"
        st.rerun()
    st.caption(
        "Bâtiment universitaire réel (jeu public PLEIAData, un an de mesures horaires). "
        "Le calcul est exécuté réellement sous vos yeux — rien n'est simulé ni préenregistré."
    )
    if load_product_payload(root) is not None:
        if st.button("Reprendre le dernier diagnostic journalisé"):
            st.session_state["page"] = "tableau"
            st.rerun()


# ------------------------------------------------------------------- execution

def _bank_table(rows: dict[str, dict[str, object]]) -> pd.DataFrame:
    display = []
    for row in rows.values():
        display.append({
            "Structure": row["model"],
            "Complexité (paramètres)": row["n_parameters"],
            "État": row["status"],
            "Écart validation (°C)": row.get("val_rmse"),
            "Statut final": row.get("final", ""),
        })
    return pd.DataFrame(display)


def _bank_chart(points: list[dict[str, object]], selected: str | None, article: dict | None):
    layers = []
    if points:
        frame = pd.DataFrame(points)
        frame["rôle"] = frame["model"].map(
            lambda name: "retenue" if selected and name == selected else "candidate"
        )
        base = alt.Chart(frame).mark_circle(size=120).encode(
            x=alt.X("n_parameters:Q", title="Complexité du modèle (nombre de paramètres)"),
            y=alt.Y("val_rmse:Q", title="Écart de validation (°C)", scale=alt.Scale(zero=False)),
            color=alt.Color("rôle:N", scale=alt.Scale(domain=["candidate", "retenue", "référence article"],
                                                      range=["#4c78a8", "#f58518", "#54a24b"]),
                            legend=alt.Legend(title="")),
            tooltip=["model", "n_parameters", alt.Tooltip("val_rmse:Q", format=".3f")],
        )
        layers.append(base)
    if article is not None:
        ref = pd.DataFrame([{
            "model": "référence article (4R3C)", "n_parameters": article["n_parameters"],
            "val_rmse": article["val_rmse"], "rôle": "référence article",
        }])
        layers.append(
            alt.Chart(ref).mark_point(size=220, shape="diamond", filled=True).encode(
                x="n_parameters:Q", y="val_rmse:Q",
                color=alt.Color("rôle:N", scale=alt.Scale(domain=["candidate", "retenue", "référence article"],
                                                          range=["#4c78a8", "#f58518", "#54a24b"]), legend=None),
                tooltip=["model", alt.Tooltip("val_rmse:Q", format=".3f")],
            )
        )
    if not layers:
        return None
    return alt.layer(*layers).properties(height=340)


def _render_execution(root: Path) -> None:
    st.title("Analyse en direct")
    st.caption("Chaque ligne reflète un calcul réellement en cours — aucune progression simulée.")
    payload = st.session_state.get("payload")
    if payload is not None and not st.session_state.get("run_pending"):
        st.success("L'analyse est terminée et journalisée.")
        if st.button("Ouvrir le tableau de bord", type="primary"):
            st.session_state["page"] = "tableau"
            st.rerun()
        if st.button("Relancer l'analyse en direct"):
            st.session_state["run_pending"] = True
            st.rerun()
        return

    upload = st.session_state.get("upload")
    config = DemoConfig()
    if upload is None:
        generator = run_live_pipeline(root, config)
    else:
        generator = run_live_pipeline(
            root, config,
            uploaded_hourly=upload["hourly"],
            upload_provenance=upload["provenance"],
            uploaded_plan_paths=upload["plan_paths"] or None,
        )

    plans_status = st.status(STAGE_TITLES["plans"], expanded=True)
    data_status = st.status(STAGE_TITLES["data"], expanded=False)
    st.subheader(STAGE_TITLES["bank"])
    st.caption("Une ligne par structure candidate ; chaque point du graphique apparaît quand un calage se termine.")
    progress_bar = st.progress(0.0, text="Banc en attente")
    table_placeholder = st.empty()
    chart_placeholder = st.empty()
    selection_placeholder = st.empty()
    drift_status = st.status(STAGE_TITLES["drift"], expanded=False)
    scenario_status = st.status(STAGE_TITLES["scenarios"], expanded=False)

    bank_rows: dict[str, dict[str, object]] = {}
    chart_points: list[dict[str, object]] = []
    n_structures = 1
    completed_fits = 0
    total_fits = 1
    selected_model: str | None = None
    article_ref: dict | None = None
    started = time.perf_counter()

    final_payload = None
    try:
        while True:
            event = next(generator)
            kind = event["kind"]
            if kind == "stage" and event["stage"] == "plans":
                if event["status"] == "done":
                    plans_status.update(
                        label=f"{STAGE_TITLES['plans']} — {event['n_plans']} fichiers inventoriés, "
                        "validation humaine requise avant usage géométrique",
                        state="complete", expanded=False)
            elif kind == "plan":
                detail = f"{event['filename']}"
                if event.get("vector_drawing_count"):
                    detail += f" — {event['vector_drawing_count']} tracés vectoriels"
                if event.get("detected_scale"):
                    detail += f", échelle {event['detected_scale']}"
                plans_status.write(detail)
            elif kind == "stage" and event["stage"] == "data" and event["status"] == "start":
                data_status.update(label=f"{STAGE_TITLES['data']} — {event['source']}", state="running", expanded=True)
            elif kind == "data_progress":
                data_status.write(f"{event['rows']:,} lignes lues".replace(",", " "))
            elif kind == "data_summary":
                data_status.update(
                    label=(
                        f"{STAGE_TITLES['data']} — {event['rows']:,} heures, {event['missing_hours']} heures manquantes, "
                        f"calage {event['splits']['train']} h / vérification {event['splits']['validation']} h / "
                        f"test {event['splits']['test']} h"
                    ).replace(",", " "),
                    state="complete", expanded=False)
            elif kind == "stage" and event["stage"] == "bank" and event["status"] == "start":
                structures = event["structures"]
                n_structures = len(structures)
                total_fits = n_structures * event["n_starts"]
                for item in structures:
                    bank_rows[item["model"]] = {
                        "model": item["model"], "n_parameters": item["n_parameters"],
                        "status": "en attente", "final": "",
                    }
                table_placeholder.dataframe(_bank_table(bank_rows), hide_index=True, width="stretch")
            elif kind == "fit_start":
                bank_rows[event["model"]]["status"] = f"calage en cours — départ {event['start_id']}/{event['n_starts']}"
                table_placeholder.dataframe(_bank_table(bank_rows), hide_index=True, width="stretch")
            elif kind == "fit_done":
                completed_fits += 1
                progress_bar.progress(
                    min(completed_fits / total_fits, 1.0),
                    text=f"{completed_fits}/{total_fits} calages effectués — {time.perf_counter() - started:.0f} s",
                )
            elif kind == "structure_done":
                row = bank_rows[event["model"]]
                row["status"] = "terminé"
                row["val_rmse"] = round(event["val_rmse"], 3)
                row["final"] = "candidate"
                chart_points.append({
                    "model": event["model"], "n_parameters": event["n_parameters"],
                    "val_rmse": event["val_rmse"],
                })
                table_placeholder.dataframe(_bank_table(bank_rows), hide_index=True, width="stretch")
                chart = _bank_chart(chart_points, selected_model, article_ref)
                if chart is not None:
                    chart_placeholder.altair_chart(chart, width="stretch")
            elif kind == "stage" and event["stage"] == "bank" and event["status"] == "done":
                for excluded in event["excluded"]:
                    bank_rows[excluded["model"]]["final"] = "écartée : " + excluded["reason"]
                table_placeholder.dataframe(_bank_table(bank_rows), hide_index=True, width="stretch")
            elif kind == "selection":
                selected_model = event["model"]
                article_ref = event.get("article_reference")
                bank_rows[selected_model]["final"] = "retenue (meilleur compromis)"
                table_placeholder.dataframe(_bank_table(bank_rows), hide_index=True, width="stretch")
                chart = _bank_chart(chart_points, selected_model, article_ref)
                if chart is not None:
                    chart_placeholder.altair_chart(chart, width="stretch")
                message = f"Étape 4 — Sélection : **{selected_model}** retenue par le banc."
                if article_ref is not None:
                    message += (
                        " Le losange vert est la référence publiée de l'article (structure 4R3C) : "
                        "c'est elle qui sert de jumeau d'exploitation, le banc mesure la sensibilité du calage."
                    )
                selection_placeholder.success(message)
            elif kind == "twin":
                selection_placeholder.success(
                    f"Étape 4 — Sélection : jumeau d'exploitation **{event['model']}** "
                    f"(écart validation {event['val_rmse']:.2f} °C, test {event['test_rmse']:.2f} °C)."
                )
            elif kind == "stage" and event["stage"] == "drift" and event["status"] == "start":
                drift_status.update(state="running", expanded=True)
                drift_status.write("Simulation du jumeau sur l'année complète…")
            elif kind == "drift_done":
                drift_status.write(event["message"])
                drift_status.update(label=f"{STAGE_TITLES['drift']} — terminé", state="complete", expanded=True)
            elif kind == "stage" and event["stage"] == "scenarios" and event["status"] == "start":
                scenario_status.update(state="running", expanded=True)
            elif kind == "scenario_done":
                if event["applicable"] and event.get("delta_energy_pct") is not None:
                    scenario_status.write(
                        f"{event['title']} : {event['delta_energy_pct']:+.1f} % d'énergie de chauffage à confort identique."
                    )
                elif event["applicable"]:
                    scenario_status.write(f"{event['title']} : calculé.")
                else:
                    scenario_status.write(f"{event['title']} : non interprétable — {event['reason_if_not']}")
            elif kind == "payload_ready":
                scenario_status.update(label="Scénarios d'intervention — terminés", state="complete", expanded=False)
    except StopIteration as stop:
        final_payload = stop.value

    st.session_state["payload"] = final_payload
    st.session_state["run_pending"] = False
    st.session_state["onboarding_done"] = False
    elapsed = time.perf_counter() - started
    st.success(f"Étape 6 — Analyse terminée et journalisée en {elapsed:.0f} s. Le tableau de bord est prêt.")
    if st.button("Ouvrir le tableau de bord", type="primary"):
        st.session_state["page"] = "tableau"
        st.rerun()


# ------------------------------------------------------------------- dashboard

def _render_onboarding(root: Path, payload: dict) -> bool:
    if st.session_state.get("onboarding_done"):
        return True
    st.title("Avant le diagnostic : 4 questions")
    st.write(
        "Ces réponses délimitent ce que le diagnostic a le droit d'affirmer. "
        "Répondre « inconnu » est une réponse valable : le tableau de bord s'y adapte."
    )
    questions = payload.get("onboarding_questions", [])
    with st.form("onboarding"):
        answers: dict[str, str] = {}
        for question in questions:
            st.markdown(f"**{question['prompt']}**")
            st.caption(question["why_needed"])
            answers[question["key"]] = st.radio(
                question["key"], ["Je peux le fournir", "Inconnu pour l'instant"],
                horizontal=True, label_visibility="collapsed", index=1,
            )
        submitted = st.form_submit_button("Valider et ouvrir le tableau de bord", type="primary")
    if submitted:
        journal = root / "runs" / "demo" / "latest" / "onboarding_answers.json"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(json.dumps(answers, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        st.session_state["onboarding_done"] = True
        st.rerun()
    return False


def _metric_help(card: dict) -> str:
    return f"Fourchette : {card['lower']:.2f} à {card['upper']:.2f} {card['unit']} — {card['method']}"


def _render_summary(payload: dict) -> None:
    drift = payload["drift"]
    switch = drift.get("structural_switch")
    heat_loss = payload["indicators"]["heat_loss"]
    test_metric = payload["twin"]["metrics"]["test_rmse"]
    validation_metric = payload["twin"]["metrics"]["validation_rmse"]
    scenarios = [s for s in payload["scenarios"] if s["applicable"] and s["delta_energy_pct"] is not None]
    best = min(scenarios, key=lambda s: s["delta_energy_pct"]) if scenarios else None

    columns = st.columns(4)
    with columns[0]:
        if switch:
            date = pd.Timestamp(switch["date"]).strftime("%d %b %Y")
            st.metric("Changement de comportement", date,
                      delta=f"glissement dès le {pd.Timestamp(switch['onset_date']).strftime('%d %b')}" if switch.get("onset_date") else None,
                      delta_color="off",
                      help=f"Sortie durable de la bande calibrée (±{switch['train_band_halfwidth_c']:.1f} °C, {switch['persistence_days']} jours consécutifs).")
        else:
            st.metric("Changement de comportement", "non détecté", help="Aucune sortie durable de la bande calibrée.")
    with columns[1]:
        if not heat_loss.get("physically_readable"):
            st.metric("Niveau de déperdition", "non lisible", help="Le calage retenu n'a pas de lecture physique de l'enveloppe.")
        elif heat_loss.get("robustness_note"):
            st.metric("Niveau de déperdition", f"{heat_loss['value']:.0f} W/°C",
                      delta="valeur non robuste entre calages", delta_color="off",
                      help=heat_loss["robustness_note"])
        else:
            st.metric("Niveau de déperdition", f"{heat_loss['value']:.0f} W/°C",
                      delta=(f"{heat_loss['direct_path_share']*100:.0f} % par l'air direct"
                             if heat_loss.get("direct_path_share") else None),
                      delta_color="off", help=_metric_help(heat_loss))
    with columns[2]:
        st.metric("Précision du jumeau (test)", f"±{test_metric['value']:.2f} °C",
                  delta=f"±{validation_metric['value']:.1f} °C pendant la dérive d'automne",
                  delta_color="off", help=_metric_help(test_metric))
    with columns[3]:
        if best is not None:
            spread = (best.get("dispersion") or {}).get("delta_energy_pct") or {}
            spread_text = (
                f" Fourchette entre calages : {spread['q05']:+.1f} à {spread['q95']:+.1f} %."
                if spread else ""
            )
            st.metric("Meilleure économie simulée", f"{best['delta_energy_pct']:+.0f} %",
                      delta=best["title"], delta_color="off",
                      help="Énergie de chauffage à confort identique, simulation conditionnelle — pas une garantie." + spread_text)
        else:
            st.metric("Meilleure économie simulée", "aucun effet exploitable")


def _render_drift_section(root: Path, payload: dict) -> None:
    st.header("Quand votre bâtiment change de comportement")
    drift = payload["drift"]
    st.info(drift["message"])
    daily = load_drift_daily(root)
    if daily is None:
        st.caption("Courbe indisponible : relancez l'analyse.")
        return
    frame = daily.reset_index().rename(columns={"Tin_measured": "mesuré", "Tin_estimated": "attendu (jumeau calibré)"})
    long = frame.melt(id_vars=["Date"], value_vars=["mesuré", "attendu (jumeau calibré)"],
                      var_name="série", value_name="température")
    lines = alt.Chart(long).mark_line().encode(
        x=alt.X("Date:T", title=None),
        y=alt.Y("température:Q", title="Température intérieure (°C, moyenne journalière)", scale=alt.Scale(zero=False)),
        color=alt.Color("série:N", scale=alt.Scale(range=["#4c78a8", "#f58518"]), legend=alt.Legend(title="", orient="top")),
        tooltip=["Date:T", "série:N", alt.Tooltip("température:Q", format=".1f")],
    ).properties(height=380)
    layers = [lines]
    switch = drift.get("structural_switch")
    if switch:
        rupture = pd.DataFrame([{"Date": pd.Timestamp(switch["timestamp"]), "libellé": "rupture"}])
        layers.append(alt.Chart(rupture).mark_rule(color="#e45756", strokeWidth=2).encode(x="Date:T"))
        if switch.get("onset_date"):
            onset = pd.DataFrame([{"Date": pd.Timestamp(switch["onset_date"])}])
            layers.append(alt.Chart(onset).mark_rule(color="#e45756", strokeDash=[6, 4]).encode(x="Date:T"))
    st.altair_chart(alt.layer(*layers), width="stretch")
    cumulative = frame[["Date", "cumulative_gap_c_h"]].dropna()
    area = alt.Chart(cumulative).mark_area(opacity=0.5, color="#e45756").encode(
        x=alt.X("Date:T", title=None),
        y=alt.Y("cumulative_gap_c_h:Q", title="Écart cumulé (°C·h)"),
        tooltip=["Date:T", alt.Tooltip("cumulative_gap_c_h:Q", format=",.0f")],
    ).properties(height=160)
    st.altair_chart(area, width="stretch")
    st.caption(
        "Trait plein rouge : rupture confirmée ; pointillé : début du glissement. "
        f"Écart cumulé en fin d'année : {drift['cumulative_final_c_h']:,.0f} °C·h — {drift['direction']}.".replace(",", " ")
    )


def _render_identified(payload: dict) -> None:
    st.header("Ce que le modèle a identifié")
    indicators = payload["indicators"]
    left, right = st.columns(2)
    with left:
        st.markdown("**Déperditions**")
        st.write(indicators["heat_loss"]["sentence"])
        if indicators["heat_loss"].get("robustness_note"):
            st.warning(indicators["heat_loss"]["robustness_note"])
        elif indicators["heat_loss"].get("physically_readable"):
            st.caption(_metric_help(indicators["heat_loss"]))
        hours = indicators.get("response_time_hours")
        st.markdown("**Réactivité au chauffage**")
        if hours is not None:
            st.write(f"Le bâtiment atteint l'essentiel de son échauffement en environ {hours:.0f} h après un changement de puissance.")
        else:
            st.write("La réactivité au chauffage n'a pas de lecture fiable sur ce calage.")
        st.caption("Temps simulé sur le jumeau calibré, pas une mesure directe.")
    with right:
        st.markdown("**Ce que le modèle ne peut pas distinguer**")
        st.write(indicators["cannot_distinguish_text"])
        st.markdown("**Fiabilité du diagnostic**")
        st.write(indicators["reliability_text"])


def _render_scenarios(payload: dict) -> None:
    st.header("Scénarios d'intervention (simulation conditionnelle)")
    st.caption(
        "Chaque scénario modifie les propriétés identifiées du jumeau, puis simule l'année mesurée à confort identique. "
        "Ce sont des ordres de grandeur conditionnels, pas des promesses de chantier."
    )
    rows = []
    for scenario in payload["scenarios"]:
        if not scenario["applicable"]:
            continue
        if scenario["negligible_energy"] and scenario["negligible_temperature"]:
            continue
        spread = (scenario.get("dispersion") or {}).get("delta_energy_pct") or {}
        rows.append({
            "Scénario": scenario["title"],
            "delta_pct": scenario["delta_energy_pct"],
            "lo": spread.get("q05", scenario["delta_energy_pct"]),
            "hi": spread.get("q95", scenario["delta_energy_pct"]),
        })
    if rows:
        frame = pd.DataFrame(rows)
        bars = alt.Chart(frame).mark_bar(color="#4c78a8").encode(
            y=alt.Y("Scénario:N", sort="x", title=None),
            x=alt.X("delta_pct:Q", title="Énergie de chauffage à confort identique (%)"),
            tooltip=["Scénario", alt.Tooltip("delta_pct:Q", format="+.1f"),
                     alt.Tooltip("lo:Q", format="+.1f", title="fourchette basse"),
                     alt.Tooltip("hi:Q", format="+.1f", title="fourchette haute")],
        )
        ticks = alt.Chart(frame).mark_errorbar(color="#e45756", ticks=True).encode(
            y=alt.Y("Scénario:N", sort=None, title=None),
            x=alt.X("lo:Q", title=""), x2="hi:Q",
        )
        st.altair_chart((bars + ticks).properties(height=90 + 50 * len(rows)), width="stretch")
    for scenario in payload["scenarios"]:
        if scenario["applicable"] and scenario["negligible_energy"] and scenario["negligible_temperature"]:
            st.write(f"— {scenario['title']} : effet négligeable sur ce bâtiment (dit explicitement plutôt qu'affiché en 10⁻⁷).")
        if scenario["applicable"] and scenario.get("note"):
            st.caption(f"{scenario['title']} : {scenario['note']}")
        if not scenario["applicable"]:
            st.write(f"— {scenario['title']} : non interprétable. {scenario['reason_if_not']}")
    st.caption("Les fourchettes proviennent de calages indépendants du même comportement ; elles sous-estiment l'incertitude totale.")


def _render_method_detail(root: Path, payload: dict) -> None:
    with st.expander("Détail méthodologique (rigueur complète)", expanded=False):
        st.markdown("**Jumeau d'exploitation.** " + payload["twin"]["policy"])
        st.markdown(
            f"- Structure : `{payload['twin']['structure_label']}` — source `{payload['twin']['twin_source']}`, "
            f"run `{payload['run_source']}`\n"
            f"- Écart validation : {payload['twin']['metrics']['validation_rmse']['value']:.3f} °C "
            f"[{payload['twin']['metrics']['validation_rmse']['lower']:.3f} ; {payload['twin']['metrics']['validation_rmse']['upper']:.3f}] ; "
            f"test : {payload['twin']['metrics']['test_rmse']['value']:.3f} °C "
            f"[{payload['twin']['metrics']['test_rmse']['lower']:.3f} ; {payload['twin']['metrics']['test_rmse']['upper']:.3f}] "
            "(bootstrap par blocs de 24 h, 300 réplications)"
        )
        st.markdown("**Verdict de reproduction (référence scellée).** Route B — identification sensible à l'initialisation ; "
                    "verdict et hachages dans `runs/m4/verdict.json`, banc complet 32 départs dans `runs/m4/multistart/`.")
        bank = payload["bank"]
        st.markdown(
            f"**Banc exécuté en direct.** {len(bank['rows'])} structures × {bank['n_starts']} départs ; "
            "sélection par structure au meilleur calage d'entraînement, classement entre structures par critère "
            "d'information sur la période de vérification ; "
            f"seuil d'admissibilité : {bank['admissibility_threshold_mse']:.2f} (2× la médiane du banc)."
        )
        st.dataframe(pd.DataFrame(bank["rows"]).drop(columns=["elapsed_s"], errors="ignore"),
                     hide_index=True, width="stretch")
        if bank["excluded"]:
            st.markdown("**Structures écartées du classement :**")
            for item in bank["excluded"]:
                st.write(f"— {item['model']} : {item['reason']} (calage train {item['train_mse']:.2f})")
        duplicates = [row["model"] for row in bank["rows"] if row.get("duplicate_of")]
        if duplicates:
            st.caption("Étiquettes dupliquées conservées volontairement : " + ", ".join(duplicates))
        st.markdown(
            "**Dérive.** Simulation en boucle ouverte sur l'année ; bande calibrée = médiane ± 3 écarts robustes "
            "des moyennes journalières de calage ; rupture = sortie persistante 14 jours ; "
            "convention du résidu : mesuré − estimé."
        )
        st.markdown(
            "**Scénarios.** Interventions sur les paramètres identifiés uniquement (jamais sur la météo ni les mesures) ; "
            "énergie à confort identique obtenue en inversant exactement le nœud d'air du modèle discret ; "
            "fourchettes = plage entre calages indépendants du même comportement."
        )
        st.markdown(f"**Géométrie.** Statut : `{payload['geometry_status']}` — aucune surface issue des plans "
                    "n'alimente le modèle sans validation humaine (`runs/m6/geometry_review_request.json`).")
        st.markdown(f"**Données.** {json.dumps(payload['dataset'], ensure_ascii=False)}")


def _render_chat(root: Path) -> None:
    st.header("Interroger le diagnostic")
    query = st.text_input("Votre question", placeholder="Ex. Quand le bâtiment décroche-t-il ?")
    if st.button("Poser la question", type="primary"):
        if not query.strip():
            st.warning("Saisissez une question.")
            return
        card = product_answer(query, root)
        if card.kind == "answer":
            st.success(card.text)
        elif card.kind == "blocked":
            st.error(card.text)
        else:
            st.warning(card.text)
        if card.estimates:
            st.dataframe(pd.DataFrame([{
                "Valeur": f"{item.value:.2f}", "Fourchette": f"{item.lower:.2f} – {item.upper:.2f}",
                "Unité": item.unit, "Période": item.period, "Méthode": item.method, "Source": item.run_source,
            } for item in card.estimates]), hide_index=True, width="stretch")
        if card.alternative_text:
            st.info(card.alternative_text)
            if card.alternative_estimates:
                st.dataframe(pd.DataFrame([{
                    "Valeur": f"{item.value:.2f}", "Fourchette": f"{item.lower:.2f} – {item.upper:.2f}",
                    "Unité": item.unit, "Période": item.period, "Méthode": item.method, "Source": item.run_source,
                } for item in card.alternative_estimates]), hide_index=True, width="stretch")
        if card.scope_note:
            st.caption(card.scope_note)


def _render_dashboard(root: Path) -> None:
    payload = st.session_state.get("payload") or load_product_payload(root)
    if payload is None:
        st.error("Aucun diagnostic disponible. Lancez l'analyse depuis l'accueil.")
        if st.button("Retour à l'accueil"):
            st.session_state["page"] = "accueil"
            st.rerun()
        return
    if not _render_onboarding(root, payload):
        return

    st.title("Diagnostic thermique du bâtiment")
    st.caption(f"Source du diagnostic : `{payload['run_source']}` — chaque chiffre est traçable jusqu'à son run.")
    st.warning(payload["indicators"]["reliability_text"])

    _render_summary(payload)
    st.divider()
    _render_drift_section(root, payload)
    st.divider()
    _render_identified(payload)
    st.divider()
    _render_scenarios(payload)
    st.divider()
    _render_method_detail(root, payload)
    st.divider()
    _render_chat(root)
    st.divider()
    if st.button("Revenir à l'accueil"):
        st.session_state["page"] = "accueil"
        st.rerun()
