"""Owner-facing chat that acts as a guide.

Answers explain what a value means, what it implies, and what to look at next —
across two domains from real data: the thermal diagnosis (journaled payload) and
the renovation costing (deterministic engine). Out-of-scope questions get a
refusal plus the closest thing the tool can actually answer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import unicodedata

from .dashboard_contract import IntervalEstimate
from .live_run import load_product_payload
from .validation_gate import M4ValidationError, require_validated_m4


@dataclass(frozen=True)
class ProductCard:
    kind: str  # "answer" | "refusal" | "blocked"
    text: str
    run_source: str | None
    estimates: tuple[IntervalEstimate, ...] = ()
    scope_note: str | None = None
    alternative_text: str | None = None
    alternative_estimates: tuple[IntervalEstimate, ...] = ()

    def __post_init__(self) -> None:
        if self.kind == "answer" and not self.run_source:
            raise ValueError("A substantive answer requires a run source.")
        if self.kind != "answer" and self.estimates:
            raise ValueError("A refusal cannot expose direct estimates; use the alternative fields.")
        if self.alternative_estimates and not self.run_source:
            raise ValueError("A served alternative requires the run source it comes from.")


def _normalized(text: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(character)
    )


def money(value) -> str:
    return "€" + format(int(round(value)), ",d")


def _interval(card: dict, run_source: str) -> IntervalEstimate:
    return IntervalEstimate(
        value=float(card["value"]), lower=float(card["lower"]), upper=float(card["upper"]),
        unit=str(card["unit"]), period=str(card["period"]), method=str(card["method"]),
        run_source=run_source,
    )


def _heat_loss_estimate(payload: dict) -> IntervalEstimate | None:
    card = payload["indicators"]["heat_loss"]
    if not card.get("physically_readable"):
        return None
    return _interval(card, str(payload["run_source"]))


def _twin_metric(payload: dict, key: str) -> IntervalEstimate:
    return _interval(payload["twin"]["metrics"][key], str(payload["run_source"]))


def _blocked(error: Exception) -> ProductCard:
    return ProductCard(
        kind="blocked",
        text="I cannot answer: the reference validation is unavailable or the diagnostic has not been run yet.",
        run_source=None,
        scope_note=str(error),
    )


def product_answer(query: str, project_root: Path | str, journal_name: str = "latest") -> ProductCard:
    try:
        require_validated_m4(project_root)
    except (M4ValidationError, FileNotFoundError, ValueError) as error:
        return _blocked(error)
    payload = load_product_payload(project_root, journal_name=journal_name)
    if payload is None and journal_name != "reference":
        payload = load_product_payload(project_root, journal_name="reference")
    if payload is None:
        return _blocked(FileNotFoundError("No journaled diagnostic: run the analysis from the home screen first."))
    from .renovation import renovation_report
    reno = renovation_report(project_root)
    b = reno["building"]
    run_source = str(payload["run_source"])
    normalized = _normalized(query)

    def has(*words: str) -> bool:
        return any(word in normalized for word in words)

    heat_loss = _heat_loss_estimate(payload)
    heat_loss_sentence = payload["indicators"]["heat_loss"].get("sentence", "")
    best = reno["scenarios"][0]

    # ---- refusals (kept), now explanatory ------------------------------------
    if has("wall", "walls", "facade", "window", "glazing", "specific wall", "north wall"):
        alt = (heat_loss,) if heat_loss else ()
        return ProductCard(
            kind="refusal",
            text=("The diagnosis works from a single average indoor temperature, so it reads the building as a whole and "
                  "cannot split the loss between one wall, the roof or the windows. Putting a figure on the north wall "
                  "specifically would be made up."),
            run_source=run_source if alt else None,
            scope_note=payload["indicators"]["cannot_distinguish_text"],
            alternative_text=("What I can give you instead is the building's overall heat-loss level, with its range — and it "
                              "already tells the story: " + heat_loss_sentence) if alt else
                             "What I can give you instead: the overall heat-loss level (not readable on this calibration).",
            alternative_estimates=alt,
        )
    if has("guarantee", "guaranteed", "promise", "certain saving", "for sure"):
        return ProductCard(
            kind="refusal",
            text=("I cannot promise a guaranteed euro figure: the model describes the measured thermal behaviour, not your "
                  "energy contract or the real execution of works. What it does give you is a defensible, computed order of "
                  "magnitude to take to a professional."),
            run_source=run_source,
            scope_note="Scenario figures are conditional on the calibrated model and standard assumptions, not a quote.",
            alternative_text=(f"For example, the best-ROI option — {best['title']} — is computed at about {money(best['savings_eur_year'])} "
                              f"per year saved (roughly {best['energy_saved_pct']}% of heating energy) and a {best['payback_years']}-year payback "
                              "(details in the decision table)."),
        )
    if has("cause", "why did", "culprit", "responsible", "blame"):
        switch = payload["drift"].get("structural_switch")
        return ProductCard(
            kind="refusal",
            text=("The measurements can date when the building changed, but not why: occupancy, settings, a boiler fault or a "
                  "ventilation change all look alike from indoor temperature alone. That is exactly what a site visit resolves."),
            run_source=run_source if switch else None,
            scope_note="A dated break is a signal to investigate, not a cause.",
            alternative_text=("What I can pin down is the date and size of the change: " + payload["drift"]["message"]) if switch else None,
        )

    # ---- building identity ----------------------------------------------------
    if has("dpe", "rating", "class", "energy label", "grade"):
        return ProductCard(kind="answer", run_source=run_source,
            text=(f"This building is rated DPE {b['dpe_class']} ({b['dpe_kwh_ep_m2_an']:.0f} kWh/m2/yr, {b['dpe_kg_co2_m2_an']:.0f} kgCO2/m2/yr) "
                  "— an 'energy sieve'. In practice that means high bills and emissions now, and a regulatory clock: under the "
                  "Climate & Resilience law, class-F dwellings can no longer be let from 2028. The aim is to lift it at least two "
                  "classes; the decision table shows what that costs and returns."),
            scope_note="DPE class uses the 1.9 primary-energy electricity coefficient (2026 reform).")
    if has("bill", "current cost", "cost now", "current energy", "spend", "how much do they pay"):
        k = reno["kpis"]
        return ProductCard(kind="answer", run_source=run_source,
            text=(f"At today's DPE the building's theoretical energy runs about {money(k['current_energy_eur_year'])} per year and "
                  f"{k['current_co2_t_year']:.0f} tCO2 per year for the whole building. That is the baseline every scenario is "
                  "measured against — the larger it is, the more a retrofit can claw back."),
            scope_note="Theoretical DPE consumption at an indicative gas tariff; a real bill depends on use and contract.")
    if has("what building", "which building", "identity", "address", "describe the building", "who is this"):
        return ProductCard(kind="answer", run_source=run_source,
            text=(f"{b['address']}, {b['district']} ({b['city']}): a {b['year']} {b['type'].lower()} block, {b['levels']}, "
                  f"{b['dwellings']} dwellings, {b['wall_material']} walls, {b['heating']}, {b['ventilation']}. A social-landlord asset "
                  f"rated DPE {b['dpe_class']} — which is why it ranks as a renovation priority."),
            scope_note="Real BDNB / DPE ADEME record.")

    # ---- the twin (thermal) ---------------------------------------------------
    if has("drift", "break", "switch", "diverge", "when", "decouple", "seasonal", "autumn", "date", "stop behaving"):
        sw = payload["drift"].get("structural_switch")
        implication = (" It means the building's real response parted from the calibrated model that autumn and stayed there — the "
                       "kind of shift a heating-season commissioning or a systems change produces, so the plant is the first thing "
                       "to check.") if sw else ""
        return ProductCard(kind="answer", run_source=run_source,
            text=payload["drift"]["message"] + implication,
            scope_note=f"Cumulative gap over the year: {payload['drift']['cumulative_final_c_h']:,.0f} degC.h ({payload['drift']['direction']}).")
    if has("heat loss", "heat-loss", "insulation", "envelope", "leak", "infiltration", "how leaky", "losses"):
        if heat_loss is None:
            return ProductCard(kind="refusal",
                text="The heat-loss level is not readable on this calibration (the selected solution has no physical envelope reading).",
                run_source=None, scope_note=payload["indicators"]["cannot_distinguish_text"],
                alternative_text="I can still give you the twin's accuracy and the dated drift, which carry the diagnosis.")
        share = payload["indicators"]["heat_loss"].get("direct_path_share")
        implic = (" Most of it takes a direct indoor-to-outdoor path, which points at air renewal and infiltration rather than the "
                  "walls — consistent with this building having no mechanical ventilation. A professional would test airtightness "
                  "first.") if (share and share >= 0.5) else ""
        return ProductCard(kind="answer", text=heat_loss_sentence + implic, run_source=run_source,
            estimates=(heat_loss,), scope_note=payload["indicators"]["cannot_distinguish_text"])
    if has("mass", "inertia", "response", "responsive", "reactivity", "how fast", "control", "pilotage"):
        hours = payload["indicators"].get("response_time_hours")
        text = (f"The building reaches most of a temperature change in about {hours:.0f} h — a slow thermal response. For control that "
                "favours anticipatory, schedule-based heating (start earlier, avoid on/off cycling) over reactive thermostats; on a "
                "collective plant, weather-compensated control fits.") if hours is not None else \
               "The heating response has no reliable reading on this calibration."
        return ProductCard(kind="answer", text=text, run_source=run_source,
            scope_note="Time simulated on the calibrated twin, not a direct measurement.")
    if has("accuracy", "precision", "reliab", "confidence", "how good", "trust", "error"):
        return ProductCard(kind="answer", run_source=run_source,
            text=(f"The twin tracks the building to +/-{payload['twin']['metrics']['test_rmse']['value']:.2f} degC in the test month and "
                  f"+/-{payload['twin']['metrics']['validation_rmse']['value']:.2f} degC during the autumn drift. The point is not the absolute "
                  "error — it is that the drift is far larger than the noise, which is what makes the dated change trustworthy. "
                  + payload["indicators"]["reliability_text"]),
            estimates=(_twin_metric(payload, "test_rmse"), _twin_metric(payload, "validation_rmse")))
    if has("structure", "model", "twin", "parameter", "how does it work"):
        return ProductCard(kind="answer", text=payload["twin"]["policy"], run_source=run_source,
            estimates=(_twin_metric(payload, "validation_rmse"),), scope_note=payload["indicators"]["cannot_distinguish_text"])

    # ---- recommendations & decision -------------------------------------------
    if has("subsid", "aid", "aide", "grant", "funding", "maprimerenov", "cee", "eco-pls", "eco pls", "finance", "money to help"):
        parts = ", ".join(a["name"] for a in reno["aides"][:5])
        q = "; ".join(f"{a['name']} approx {money(a['amount_eur'])} ({a['kind']})" for a in reno["aides"] if a.get("amount_eur"))
        return ProductCard(kind="answer", run_source=run_source,
            text=(f"Because it is social housing, an energy sieve, in a QPV and near a priority heat network, several schemes apply: {parts}. "
                  f"The quantified ones are {q}. Note Eco-PLS is a subsidised loan (financing), while the CEE amount is a grant that lowers the "
                  "net cost in the decision table — the payback figures already use it."),
            scope_note="Indicative amounts from public schemes; confirm per project.")
    if has("regulation", "law", "loi climat", "passoire", "2028", "rent", "let", "legal", "compliance", "urbanism", "abf"):
        chips = "; ".join(f"{c['label']} — {c['detail']}" for c in reno["regulation"][:6])
        return ProductCard(kind="answer", run_source=run_source,
            text=("Regulatory picture: " + chips + ". The binding one is the letting ban on class-F homes from 2028, which turns this from "
                  "'nice to have' into a deadline. The AC1 servitude means facade work needs the planning department's sign-off."),
            scope_note="Regulatory context from the building's BDNB attributes.")
    if has("roi", "payback", "return", "best option", "which scenario", "decision", "recommend", "table", "invest", "cheapest", "worth"):
        deep = next((s for s in reno["scenarios"] if s["key"] == "deep_retrofit"), None)
        extra = (f" At the other end, the deep retrofit to class B avoids about {deep['co2_avoided_t_30y']:,} tCO2 over 30 years for "
                 f"{money(deep['cost_eur'])} — more impact, longer payback.") if deep else ""
        return ProductCard(kind="answer", run_source=run_source,
            text=(f"Ranked by payback, the shortest is {best['title']} -> DPE {best['target_class']}: about {money(best['savings_eur_year'])}/yr saved, "
                  f"{best['co2_avoided_t_year']:.0f} tCO2/yr, {money(best['cost_eur'])} gross ({money(best['net_cost_eur'])} after the CEE grant), a "
                  f"{best['payback_years']}-year payback. That is the pragmatic first move.{extra} The table lets you weigh fast return against deep impact."),
            scope_note="Deterministic energy/CO2/cost; payback net of the CEE grant.")
    if has("retrofit", "renovation", "renovate", "scenario", "insulate", "works", "upgrade", "improve", "save", "what to do"):
        lines = "; ".join(f"{s['title']} -> {s['target_class']}: {money(s['savings_eur_year'])}/yr, {s['co2_avoided_t_year']:.0f} tCO2/yr, {s['payback_years']} yr"
                          for s in reno["scenarios"][:4])
        return ProductCard(kind="answer", run_source=run_source,
            text=("The costed options, cheapest-payback first: " + lines + ". All are carbon-virtuous over 30 years because they use bio-sourced "
                  "materials. Which one fits depends on whether you optimise for fast return or deep decarbonation."),
            scope_note="Conditional, deterministic figures; ranges in the decision table.")
    if has("neighbour", "neighbor", "neighbourhood", "neighborhood", "compare", "nearby", "others", "map", "around"):
        cls = [n["dpe_class"] for n in reno["neighbors"]]
        return ProductCard(kind="answer", run_source=run_source,
            text=(f"The five nearest buildings are rated {', '.join(cls)} within about 60 m — two are already A and C. So this F block is the "
                  "local laggard, which strengthens the case: the street is renovating around it, and public funding prioritises exactly this profile."),
            scope_note="Real DPE classes of KNN neighbours (positions approximate on the map).")

    return ProductCard(
        kind="refusal",
        text="That is outside what this diagnosis can establish from the measurements and the building record.",
        run_source=None,
        scope_note=("I can explain the building and its DPE, the dated behaviour change (the drift), the heat-loss level and what it "
                    "implies, the renovation options with their euro and CO2, the eligible subsidies and regulation, and the ROI decision."),
        alternative_text="Try: “What does DPE F mean?”, “When does the building drift?”, or “Which retrofit has the best payback?”",
    )


def serialize_product_card(card: ProductCard) -> dict:
    return asdict(card)
