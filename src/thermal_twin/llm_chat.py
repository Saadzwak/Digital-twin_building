"""LLM-backed product guide, grounded strictly on the computed diagnosis.

The chat sends the *entire computed payload* (identified parameters, dated drift,
heat-loss level, renovation scenarios, ROI, subsidies, regulation, building
record, uncertainties) to the OpenAI Chat Completions API as system context, with
a strict instruction to answer only from those values, never to invent a figure,
to cite the quantity each answer derives from, and to refuse (with an alternative)
when a question falls outside the diagnosis.

Provenance is preserved: the natural-language *text* comes from the model, but the
numeric estimates rendered under the answer keep coming from the payload via the
deterministic engine — the model never becomes the source of a displayed number.

If ``OPENAI_API_KEY`` is not set, ``llm_available`` returns False and the caller
falls back to the deterministic guide. No key, no crash.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

API_URL = "https://api.openai.com/v1/chat/completions"
# gpt-5.6 routes to Sol; gpt-5.6-terra is the low-latency variant, better for a
# live demo. Override with OPENAI_CHAT_MODEL.
DEFAULT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "gpt-5.6-terra")


def api_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    return key.strip() if key else None


def llm_available() -> bool:
    return bool(api_key())


def model_name() -> str:
    return os.environ.get("OPENAI_CHAT_MODEL", DEFAULT_MODEL)


def build_context(payload: dict, reno: dict) -> dict:
    """The full computed diagnosis, compacted to what the guide may cite."""

    ind = payload.get("indicators", {})
    hl = ind.get("heat_loss", {})
    twin = payload.get("twin", {})
    metrics = twin.get("metrics", {})
    drift = payload.get("drift", {})
    b = reno.get("building", {})
    return {
        "run_source": payload.get("run_source"),
        "building": {
            "address": b.get("address"), "district": b.get("district"), "city": b.get("city"),
            "year": b.get("year"), "type": b.get("type"), "levels": b.get("levels"),
            "dwellings": b.get("dwellings"), "living_area_m2": b.get("living_area_m2"),
            "footprint_m2": b.get("footprint_m2"), "wall_material": b.get("wall_material"),
            "heating": b.get("heating"), "ventilation": b.get("ventilation"),
            "dpe_class": b.get("dpe_class"), "dpe_kwh_ep_m2_an": b.get("dpe_kwh_ep_m2_an"),
            "dpe_kg_co2_m2_an": b.get("dpe_kg_co2_m2_an"), "rnb_id": b.get("rnb_id"),
            "in_qpv": b.get("in_qpv"), "social_landlord": True,
        },
        "current_cost_and_emissions": reno.get("kpis", {}),
        "heat_loss": {
            "physically_readable": hl.get("physically_readable"),
            "value_w_per_c": hl.get("value"), "unit": hl.get("unit"),
            "range": [hl.get("lower"), hl.get("upper")],
            "direct_path_share": hl.get("direct_path_share"),
            "sentence": hl.get("sentence"), "robustness_note": hl.get("robustness_note"),
        },
        "responsiveness_hours": ind.get("response_time_hours"),
        "cannot_distinguish": ind.get("cannot_distinguish_text"),
        "reliability": ind.get("reliability_text"),
        "dated_drift": {
            "message": drift.get("message"),
            "structural_switch": drift.get("structural_switch"),
            "cumulative_gap_c_h": drift.get("cumulative_final_c_h"),
            "direction": drift.get("direction"),
        },
        "digital_twin": {
            "structure": twin.get("structure_label"), "policy": twin.get("policy"),
            "consistent_with_selection": twin.get("consistent_with_selection"),
            "validation_rmse_c": (metrics.get("validation_rmse") or {}).get("value"),
            "test_rmse_c": (metrics.get("test_rmse") or {}).get("value"),
        },
        "renovation_scenarios": [
            {
                "title": s.get("title"), "target_class": s.get("target_class"),
                "energy_saved_pct": s.get("energy_saved_pct"),
                "savings_eur_year": s.get("savings_eur_year"),
                "co2_avoided_t_year": s.get("co2_avoided_t_year"),
                "co2_avoided_t_30y": s.get("co2_avoided_t_30y"),
                "cost_eur": s.get("cost_eur"), "cee_grant_eur": s.get("cee_grant_eur"),
                "net_cost_eur": s.get("net_cost_eur"), "payback_years": s.get("payback_years"),
                "note": s.get("note"),
            }
            for s in reno.get("scenarios", [])
        ],
        "subsidies": [
            {"name": a.get("name"), "kind": a.get("kind"), "amount_eur": a.get("amount_eur"),
             "condition": a.get("condition"), "source": a.get("source")}
            for a in reno.get("aides", [])
        ],
        "regulation": [
            {"label": c.get("label"), "detail": c.get("detail")} for c in reno.get("regulation", [])
        ],
        "neighbours": [
            {"dpe_class": n.get("dpe_class"), "distance_m": n.get("distance_m")}
            for n in reno.get("neighbors", [])
        ],
        "assumptions": reno.get("assumptions", []),
        "geometry_status": payload.get("geometry_status"),
    }


SYSTEM_INSTRUCTIONS = """You are the in-product guide for a thermal-diagnosis and renovation dashboard about ONE real social-housing building. A user reads the dashboard and asks you questions.

Ground rules — follow them exactly:
1. Answer ONLY from the CONTEXT JSON provided below. Every number you state MUST be present in or directly derived from CONTEXT. Never invent, guess, extrapolate, or round to a figure that is not supported by CONTEXT.
2. Always make clear which quantity your answer derives from (e.g. "from the heat-loss level", "from the ROI table", "from the dated drift"), in plain words inside the answer.
3. You MAY: explain any element of the dashboard, reformulate for a non-technical reader, connect several values, and answer questions that were not pre-scripted — as long as you stay factual on the numbers.
4. Refuse when the question is outside what this diagnosis can establish: anything not about this building or its diagnosis/renovation (weather, markets, unrelated topics), a promise of guaranteed euro savings, a per-wall / per-window loss breakdown (the method uses a single average indoor temperature and cannot split the loss), or the CAUSE of the dated change (the measurements date it, they do not explain why). When you refuse, say briefly why, then propose the closest thing the tool CAN answer.
5. Be concise (2–5 sentences), plain, and calm — a control-room tone, not marketing. Do not use markdown headers or bullet lists.

Respond with STRICT JSON only, no prose outside it:
{"kind": "answer" | "refusal", "text": "your reply", "alternative_text": "for a refusal, the closest answerable thing (else empty)", "source": "short label of the CONTEXT quantity you used"}"""


def answer_llm(query: str, payload: dict, reno: dict, *, model: str | None = None, timeout: float = 25.0) -> dict | None:
    """Call the OpenAI API grounded on the computed context.

    Returns a dict {kind, text, alternative_text, source} or None on any failure
    (missing key, network error, bad JSON) so the caller can fall back cleanly.
    """

    key = api_key()
    if not key:
        return None
    context = build_context(payload, reno)
    system = SYSTEM_INSTRUCTIONS + "\n\nCONTEXT:\n" + json.dumps(context, ensure_ascii=False)
    body = json.dumps({
        "model": model or model_name(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": query.strip()[:800]},
        ],
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    request = urllib.request.Request(
        API_URL, data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError, OSError):
        return None
    kind = parsed.get("kind")
    text = parsed.get("text")
    if kind not in ("answer", "refusal") or not isinstance(text, str) or not text.strip():
        return None
    return {
        "kind": kind,
        "text": text.strip(),
        "alternative_text": (parsed.get("alternative_text") or "").strip() or None,
        "source": (parsed.get("source") or "").strip() or None,
    }
