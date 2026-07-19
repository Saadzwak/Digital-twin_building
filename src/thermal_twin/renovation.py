"""Renovation costing (€ / CO₂ / ROI) for the surveyed building.

The building record is real BDNB/DPE data. The carbon engine is the deterministic
three-component ConX method (operational + embodied + off-site avoided), ported
here as pure functions so no external stack is needed. Every displayed number is
either a real datum or an executed calculation; assumptions are labelled inline.

Sources: ADEME Base Carbone 2023; DPE order 2021 (EP electricity coef. 1.9,
2026 reform); CSTB 2023 (off-site avoided fraction); INIES (FDES static base).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

# --- Carbon factors (ADEME Base Carbone 2023, effective kgCO2/kWh EP) ----------
CLASS_MIDPOINTS_KWH_EP = {"A": 55.0, "B": 90.0, "C": 145.0, "D": 215.0, "E": 295.0, "F": 390.0, "G": 500.0}
KG_CO2_PER_KWH_EP = {"electricity": 0.034, "gas": 0.227, "oil": 0.272, "wood": 0.024,
                     "heat_network": 0.116, "heat_pump": 0.011, "unknown": 0.150}
OFFSITE_FRACTION_MEDIAN = 0.25
OFFSITE_FRACTION_LOW = 0.20
OFFSITE_FRACTION_HIGH = 0.40
SOURCES = {
    "ademe": "ADEME Base Carbone 2023",
    "dpe": "DPE order 2021 (EP electricity 1.9, 2026 reform)",
    "cstb": "CSTB 2023 — off-site construction and carbon",
    "inies": "INIES — FDES static base",
}

# --- Real surveyed building (BDNB / DPE ADEME, millésime 2025-07.a) -------------
BUILDING = {
    "building_id": "bdnb-bg-81UB-UTZE-ZP7F",
    "rnb_id": "2D9YFEZTSAC9",
    "address": "98 Rue des Sarrazins",
    "postcode": "59000",
    "city": "Lille",
    "district": "Wazemmes",
    "epci": "Métropole Européenne de Lille",
    "dept": "59",
    "iris": "593500402",
    "centroid_lon": 3.046703133419712,
    "centroid_lat": 50.624350301368295,
    "type": "Collective residential",
    "levels": "R+4",
    "year": 1978,
    "footprint_m2": 1084.0,
    "living_area_m2": 3038.0,
    "dwellings": 48,
    "wall_material": "cast concrete (20 cm)",
    "roof_material": "concrete",
    "owner_type": "bailleur_social",
    "dpe_class": "F",
    "ges_class": "F",
    "dpe_kwh_ep_m2_an": 324.0,
    "dpe_kg_co2_m2_an": 71.0,
    "dpe_id_ademe": "2259E0904747H",
    "dpe_date": "2022-04-27",
    "heating": "collective gas boiler (standard, very old)",
    "heating_energy": "gas",
    "dhw": "collective gas",
    "ventilation": "window opening (no mechanical ventilation)",
    "glazing": "double glazing, PVC, Uw 1.4",
    "u_wall": 1.0,
    "u_door": 5.8,
    "no_wall_insulation": True,
    "no_roof_insulation": True,
    "losses_w_per_k": {"walls": 55.2, "upper_floor": 40.5, "lower_floor": 35.64, "glazing": 21.34, "doors": 2.10},
    "in_qpv": True,
    "qpv_name": "Wazemmes — Secteur Sud",
    "heat_network_id": "rcu_442",
    "heat_network_priority": True,
    "heat_network_distance": "100–200 m",
    "monument_historique": False,
    "spr": False,
    "urbanism_ac1": True,
    "pmr_accessible": False,
    "risks": {"radon": "Low", "clay": "Low", "seismic": "Low"},
    # Real ConX-computed scoring values (deterministic ConX method):
    "conx_score": 96.1,
    "conx_co2_avoided_t_30y": 1727.4,
    "conx_cost_estimate_eur": 650400.0,
    "conx_eur_per_tco2": 376.52,
    # Real metered consumption (Enedis/GRDF DLE, 2024):
    "metered_elec_kwh_2024": 73837,
    "metered_gas_kwh_2024": 13376,
}

NEIGHBORS = [
    {"building_id": "bdnb-bg-EF7U-RPV1-DFZE", "dpe_class": "A", "distance_m": 33.7},
    {"building_id": "bdnb-bg-X92J-R6MV-A5GP", "dpe_class": "E", "distance_m": 46.5},
    {"building_id": "bdnb-bg-WTKV-RZ7Q-T89Y", "dpe_class": "D", "distance_m": 50.5},
    {"building_id": "bdnb-bg-E2E8-SW1W-BC51", "dpe_class": "C", "distance_m": 54.9},
    {"building_id": "bdnb-bg-GMPT-GWBZ-6XM1", "dpe_class": "D", "distance_m": 58.0},
]

# Vieux-Lille documented candidates (real BDNB, from ConX neighbourhood analysis).
VIEUX_LILLE = [
    {"building_id": "bdnb-bg-NKGA-DUZ2-J28H", "dpe_class": "F", "score": 91.1, "co2_t": 517, "cost_eur": 140000,
     "iris_lon": 3.0635, "iris_lat": 50.6403},
    {"building_id": "bdnb-bg-JBP7-PFQL-4T69", "dpe_class": "G", "score": 91.1, "co2_t": 714, "cost_eur": 140000,
     "iris_lon": 3.0662, "iris_lat": 50.6425},
    {"building_id": "bdnb-bg-7F6X-1AGX-L22Q", "dpe_class": "F", "score": 77.1, "co2_t": 300, "cost_eur": 88000,
     "iris_lon": 3.0589, "iris_lat": 50.6389},
]

# Tariffs (stated indicative assumptions, French residential 2025 order of magnitude).
GAS_TARIFF_EUR_PER_KWH = 0.11
COST_SURFACE_BASIS = "footprint"  # ConX convention: score cost uses ground footprint


def _load_fdes(project_root: Path) -> dict:
    return json.loads((Path(project_root) / "data" / "fdes_static.json").read_text(encoding="utf-8"))


def _material(fdes: dict, mid: str) -> dict:
    for m in fdes["materials"]:
        if m["id"] == mid:
            return m
    raise KeyError(mid)


def compute_exploitation(surface_m2: float, before: str, after: str, kwh_before: float | None, energy: str,
                         horizon: int = 30) -> dict:
    kwh_a = kwh_before if (kwh_before and kwh_before > 0) else CLASS_MIDPOINTS_KWH_EP.get(before, 215.0)
    kwh_b = CLASS_MIDPOINTS_KWH_EP[after]
    delta_kwh_year = (kwh_a - kwh_b) * surface_m2
    factor = KG_CO2_PER_KWH_EP.get(energy, KG_CO2_PER_KWH_EP["unknown"])
    avoided_year_kg = delta_kwh_year * factor
    return {
        "kwh_before_m2": kwh_a, "kwh_after_m2": kwh_b,
        "delta_kwh_year": delta_kwh_year,
        "co2_factor": factor,
        "avoided_year_kg": avoided_year_kg,
        "avoided_horizon_kg": avoided_year_kg * horizon,
        "horizon": horizon,
    }


def compute_incorpore(fdes: dict, items: list[tuple[str, float, str]]) -> dict:
    total_kg = 0.0
    biogenic = 0.0
    breakdown = []
    for mid, qty, label in items:
        mat = _material(fdes, mid)
        kg = float(mat["kgCO2eq_per_uf"]) * qty
        bio = float(mat.get("biogenic_co2_stored_kg") or 0.0) * qty
        total_kg += kg
        biogenic += bio
        breakdown.append({"material_id": mid, "name": mat["name"], "label": label, "quantity": qty,
                          "kg_co2_total": round(kg, 1), "fdes_id": mat["fdes_declaration_id"]})
    return {"total_kg": round(total_kg, 1), "biogenic_kg": round(biogenic, 1), "breakdown": breakdown}


def compute_offsite(incorpore: dict, fraction: float = OFFSITE_FRACTION_MEDIAN) -> dict:
    base = sum(e["kg_co2_total"] for e in incorpore["breakdown"] if e["kg_co2_total"] > 0)
    return {"base_kg": round(base, 1), "fraction": fraction, "avoided_kg": round(base * fraction, 1)}


def aides_eligibles() -> list[dict]:
    """Eligible French support schemes for this building (ported ConX rules)."""
    b = BUILDING
    dwellings = b["dwellings"]
    out = []
    # Éco-PLS is a subsidised LOAN (financing), not a grant — flagged as such.
    out.append({"code": "ECO_PLS", "name": "Éco-PLS renovation loan", "condition": "Social landlord",
                "amount_eur": dwellings * 16000, "kind": "loan", "source": "Caisse des Dépôts"})
    if b["in_qpv"]:
        out.append({"code": "ANRU", "name": "ANRU / urban policy district programme", "condition": "Building in QPV",
                    "amount_eur": None, "kind": "grant", "source": "ANRU"})
    if b["dpe_class"] in ("F", "G"):
        out.append({"code": "CEE_BS_PASSOIRE", "name": "Enhanced CEE for energy-sieve social housing",
                    "condition": f"DPE {b['dpe_class']} (energy sieve)", "amount_eur": dwellings * 2500,
                    "kind": "grant", "source": "CEE Coup de pouce"})
    if b["heat_network_priority"]:
        out.append({"code": "RCU_RACCORD", "name": "Heat-network connection bonus",
                    "condition": "Within priority development perimeter", "amount_eur": None,
                    "kind": "grant", "source": "CEE Coup de pouce RCU"})
    out.append({"code": "FONDS_VERT", "name": "Fonds vert (social/public renovation)",
                "condition": "Social housing / public asset", "amount_eur": None, "kind": "grant",
                "source": "DDT department"})
    return out


@dataclass(frozen=True)
class RenovationScenario:
    key: str
    title: str
    target_class: str
    cost_eur_per_m2: float          # indicative €/m² of footprint (ADEME renovation ranges)
    materials: list = field(default_factory=list)  # (fdes_id, quantity, label)
    note: str = ""


# Geometric envelope estimate for material quantities (stated assumption):
# footprint 1084 m², height 11 m, R+4 -> facade ~ perimeter x height; 21% glazing (real BDNB share).
_PERIM = 4.0 * (1084.0 ** 0.5) * 1.15   # slight elongation factor
_FACADE = _PERIM * 11.0
_GLAZING = round(_FACADE * 0.21)
_OPAQUE = round(_FACADE * 0.79)
_ROOF = 1084

SCENARIOS = [
    RenovationScenario(
        "ventilation_sealing", "Mechanical ventilation + air-sealing", "E", 150.0,
        [], "Targets the building's window-only ventilation (no VMC) and air leakage."),
    RenovationScenario(
        "biosourced_envelope", "Bio-sourced envelope (wall + roof insulation)", "C", 420.0,
        [("fibre-bois-rigide", _OPAQUE, "Wood-fibre external wall insulation"),
         ("ouate-cellulose-insufflee", _ROOF, "Blown cellulose roof insulation")],
        "Off-site prefabricated bio-sourced insulation on facades and roof."),
    RenovationScenario(
        "deep_retrofit", "Deep bio-sourced retrofit", "B", 600.0,
        [("fibre-bois-rigide", _OPAQUE, "Wood-fibre external wall insulation"),
         ("ouate-cellulose-insufflee", _ROOF, "Blown cellulose roof insulation"),
         ("triple-vitrage-4-12-4-12-4-argon", _GLAZING, "Triple glazing"),
         ("menuiserie-bois", _GLAZING, "Timber window frames")],
        "Full envelope + glazing + ventilation package reaching class B."),
    RenovationScenario(
        "deep_plus_network", "Deep retrofit + heat-network connection", "A", 700.0,
        [("fibre-bois-rigide", _OPAQUE, "Wood-fibre external wall insulation"),
         ("ouate-cellulose-insufflee", _ROOF, "Blown cellulose roof insulation"),
         ("triple-vitrage-4-12-4-12-4-argon", _GLAZING, "Triple glazing"),
         ("menuiserie-bois", _GLAZING, "Timber window frames")],
        "Deep retrofit plus connection to the priority urban heat network (rcu_442)."),
]


def _scenario_report(fdes: dict, s: RenovationScenario, cee_grant_eur: float) -> dict:
    b = BUILDING
    surface = b["footprint_m2"]  # ConX cost/CO₂ convention: ground footprint
    expl = compute_exploitation(surface, b["dpe_class"], s.target_class, b["dpe_kwh_ep_m2_an"], b["heating_energy"])
    inc = compute_incorpore(fdes, s.materials) if s.materials else {"total_kg": 0.0, "biogenic_kg": 0.0, "breakdown": []}
    off = compute_offsite(inc)
    net_kg = inc["total_kg"] - expl["avoided_horizon_kg"] - off["avoided_kg"]
    cost = surface * s.cost_eur_per_m2
    savings_year = expl["delta_kwh_year"] * GAS_TARIFF_EUR_PER_KWH
    net_cost = max(0.0, cost - cee_grant_eur)
    payback_gross = cost / savings_year if savings_year > 0 else None
    payback_net = net_cost / savings_year if savings_year > 0 else None
    return {
        "key": s.key, "title": s.title, "target_class": s.target_class, "note": s.note,
        "energy_saved_kwh_year": round(expl["delta_kwh_year"]),
        "energy_saved_pct": round((expl["kwh_before_m2"] - expl["kwh_after_m2"]) / expl["kwh_before_m2"] * 100),
        "savings_eur_year": round(savings_year),
        "co2_avoided_t_year": round(expl["avoided_year_kg"] / 1000.0, 1),
        "co2_avoided_t_30y": round(expl["avoided_horizon_kg"] / 1000.0),
        "embodied_t": round(inc["total_kg"] / 1000.0, 1),
        "biogenic_stored_t": round(inc["biogenic_kg"] / 1000.0, 1),
        "net_co2_t_30y": round(net_kg / 1000.0),
        "verdict": "carbon-virtuous" if net_kg < 0 else "carbon-emitting",
        "cost_eur": round(cost),
        "cee_grant_eur": round(cee_grant_eur),
        "net_cost_eur": round(net_cost),
        "payback_years_gross": round(payback_gross, 1) if payback_gross else None,
        "payback_years": round(payback_net, 1) if payback_net else None,
        "materials": inc["breakdown"],
    }


def renovation_report(project_root: Path | str) -> dict:
    fdes = _load_fdes(project_root)
    aides = aides_eligibles()
    cee = next((a["amount_eur"] for a in aides if a["code"] == "CEE_BS_PASSOIRE" and a["amount_eur"]), 0.0) or 0.0
    scenarios = [_scenario_report(fdes, s, cee) for s in SCENARIOS]
    scenarios.sort(key=lambda r: (r["payback_years"] is None, r["payback_years"] or 1e9))
    b = BUILDING
    current_energy_eur_year = round(b["dpe_kwh_ep_m2_an"] * b["footprint_m2"] * GAS_TARIFF_EUR_PER_KWH)
    current_co2_t_year = round(b["dpe_kg_co2_m2_an"] * b["footprint_m2"] / 1000.0, 1)
    best = scenarios[0]
    return {
        "building": b,
        "neighbors": NEIGHBORS,
        "vieux_lille": VIEUX_LILLE,
        "aides": aides,
        "scenarios": scenarios,
        "recommended_key": best["key"],
        "kpis": {
            "current_energy_eur_year": current_energy_eur_year,
            "current_co2_t_year": current_co2_t_year,
            "current_dpe": b["dpe_class"],
            "best_savings_eur_year": best["savings_eur_year"],
            "best_co2_t_year": best["co2_avoided_t_year"],
            "best_payback_years": best["payback_years"],
            "best_scenario": best["title"],
        },
        "regulation": _regulation(),
        "assumptions": [
            f"Gas tariff {GAS_TARIFF_EUR_PER_KWH:.2f} €/kWh (indicative, FR residential 2025).",
            "Energy/CO₂ use the DPE theoretical consumption and the ground-footprint area (ConX scoring convention).",
            "Target DPE class per scenario is a standard renovation-outcome assumption; energy, CO₂ and cost are computed.",
            "Material quantities from a facade = perimeter × height estimate (21% glazing, real BDNB share).",
            "Éco-PLS is a subsidised loan (financing), not deducted from cost; only the CEE grant reduces net cost.",
        ],
        "sources": SOURCES,
    }


def _regulation() -> list[dict]:
    b = BUILDING
    chips = []
    if b["dpe_class"] in ("F", "G"):
        chips.append({"label": "Energy sieve (DPE F)", "tone": "danger",
                      "detail": "Climate & Resilience law: class-F dwellings barred from letting in 2028."})
    if b["owner_type"] == "bailleur_social":
        chips.append({"label": "Social landlord", "tone": "info", "detail": "Priority for public renovation funding."})
    if b["in_qpv"]:
        chips.append({"label": b["qpv_name"], "tone": "info", "detail": "Urban policy district — ANRU eligible."})
    if b["heat_network_priority"]:
        chips.append({"label": "Heat network — priority", "tone": "success",
                      "detail": f"Connectable to {b['heat_network_id']} ({b['heat_network_distance']})."})
    if b["urbanism_ac1"]:
        chips.append({"label": "Urbanism servitude (AC1)", "tone": "warn",
                      "detail": "Facade work requires the urban-planning department's opinion."})
    if not b["pmr_accessible"]:
        chips.append({"label": "Not accessible (PMR)", "tone": "warn", "detail": "No step-free access declared."})
    chips.append({"label": "DPE coef. 1.9 (2026)", "tone": "muted",
                  "detail": "Class based on the 1.9 primary-energy electricity coefficient (2026 reform)."})
    return chips


def interpretation(direct_path_share: float | None, switch: dict | None,
                   response_time_hours: float | None) -> dict:
    """Phase-4 physical reading: hypotheses framed as leads, grounded in the building record.

    Combines the thermal diagnosis (dominant loss path, dated behaviour change,
    response time) with the surveyed building's declared systems (no mechanical
    ventilation, un-insulated concrete walls). These are leads for a professional,
    not conclusions.
    """
    b = BUILDING
    leads = []

    # 1. Dominant direct loss path
    if direct_path_share is not None and direct_path_share >= 0.5:
        leads.append({
            "title": f"~{round(direct_path_share*100)}% of losses take a direct indoor→outdoor path",
            "reading": (
                "Physically this points to air renewal and infiltration (and thermal bridges) dominating over "
                "conduction through the building mass. It is consistent with this building's declared "
                "window-only ventilation (no mechanical ventilation) and un-insulated cast-concrete walls "
                f"(U_wall {b['u_wall']} W/m²K, single metal door U {b['u_door']} W/m²K)."
            ),
            "check_first": (
                "A professional would first quantify airtightness (blower-door test) and the ventilation regime, "
                "then junctions/thermal bridges — before, or alongside, adding wall insulation. Air-sealing plus "
                "controlled mechanical ventilation is likely the highest-leverage, lowest-cost first move."
            ),
        })

    # 2. Dated behaviour change — ranked hypotheses
    if switch:
        leads.append({
            "title": f"Behaviour change dated to {switch.get('date')} (drift visible from {switch.get('onset_date')})",
            "reading": (
                "The building leaves its calibrated band in autumn and stays "
                f"{switch.get('offset_from_calibrated_c', 0):+.1f} °C below the model afterwards. Ranked hypotheses, "
                "most to least plausible: (1) start of the heating season — heating schedule/setpoint or the very old "
                "collective gas boiler no longer matching demand; (2) occupancy/behaviour change (window opening, "
                "presence) as it gets cold; (3) a ventilation or infiltration shift; (4) an equipment fault."
            ),
            "check_first": (
                "First check the heating plant's autumn commissioning and setpoints against the metered heat, then "
                "the ventilation regime. The very-old collective gas boiler is the primary suspect to inspect."
            ),
        })

    # 3. Response time / control implication
    if response_time_hours is not None:
        slow = response_time_hours > 100
        leads.append({
            "title": f"Slow thermal response (≈ {round(response_time_hours)} h to most of a step change)",
            "reading": (
                "A long effective response time means the indoor temperature reacts slowly to heating changes. "
                "For control this favours anticipatory, schedule-based heating (start earlier, avoid on/off cycling) "
                "over reactive thermostatting."
                + (" Note: the very long constant is partly a model extrapolation artifact and should be read as an order of magnitude." if slow else "")
            ),
            "check_first": (
                "A professional would consider weather-compensated / predictive control on the collective plant rather "
                "than per-dwelling reactive setpoints."
            ),
        })
    return {
        "leads": leads,
        "framing": "These are hypotheses to investigate on site, not conclusions.",
    }
