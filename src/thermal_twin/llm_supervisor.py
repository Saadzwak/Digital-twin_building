"""GPT-5.6 supervision layers over the deterministic engine.

Two honest QA uses of GPT-5.6, both grounded on real computed artifacts and both
gated on ``OPENAI_API_KEY`` (they report ``available: False`` without a key):

1. ``supervise_geometry`` — a **vision** check on the plan-reading step. GPT-5.6
   looks at the footprint polygon that the PyMuPDF-based reader extracted and judges
   whether it is a plausible, well-formed single-building outline or shows extraction
   artifacts. It supervises PyMuPDF's *output*; it never re-derives the geometry.
2. ``supervise_selection`` — a review of the identification **optimization**.
   GPT-5.6 evaluates the RC structure-selection bench and flags red flags
   (degeneracy, over-parameterisation, non-robustness) — a second opinion on the
   automated pick. It assesses; it never computes a parameter or a metric.

Neither ever produces an engineering number.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
import urllib.error
import urllib.request

from . import llm_chat
from .building_geometry import load_massing

_FORBIDDEN = ("pleiad", "edificio", "planta", "murcia")


def _post(messages: list, *, timeout: float = 35.0) -> dict | None:
    """One grounded JSON call to the OpenAI Chat Completions API, or None."""

    key = llm_chat.api_key()
    if not key:
        return None
    body = json.dumps({
        "model": llm_chat.model_name(),
        "messages": messages,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    request = urllib.request.Request(
        llm_chat.API_URL, data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        return json.loads(data["choices"][0]["message"]["content"])
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError, OSError):
        return None


def _clean(text) -> str:
    """Drop any sentence in which the model transcribed a source-plan label."""

    if not isinstance(text, str):
        return ""
    if any(token in text.lower() for token in _FORBIDDEN):
        kept = [part for part in text.split(". ") if not any(t in part.lower() for t in _FORBIDDEN)]
        return ". ".join(kept).strip() or "Extraction looks geometrically consistent."
    return text.strip()


def supervise_geometry(project_root: Path | str) -> dict:
    """Vision QA of the extracted footprint. Returns a verdict or available=False."""

    if not llm_chat.llm_available():
        return {"available": False}
    root = Path(project_root).resolve()
    massing = load_massing(root) or {}
    image = root / "runs" / "geometry" / "footprint_check.png"
    if not image.is_file():
        return {"available": False}
    b64 = base64.b64encode(image.read_bytes()).decode()
    n_vertices = len(massing.get("footprint", []))
    activity = [round(f.get("activity", 0), 2) for f in massing.get("floors", [])]
    summary = (
        f"An automated floor-plan reader (rasterise + concave hull) extracted this building footprint. "
        f"Reported: {n_vertices} polygon vertices, {massing.get('n_floors')} storeys, drawing scale "
        f"{massing.get('scale_label')}, footprint covers {round(massing.get('footprint_area_fraction', 0) * 100)}% "
        f"of the sheet, per-storey drawn-content activity from ground to top: {activity}."
    )
    prompt = (
        summary + " As a QA supervisor of that reader, look at the polygon in the image and judge ONLY its geometry. "
        "Is it a plausible, well-formed single-building outline, or does it show extraction artifacts "
        "(self-intersection, a captured title-block/legend rectangle, a degenerate blob, disconnected pieces)? "
        "Also state whether the vertex count and the decreasing per-storey activity are consistent with a real "
        "multi-storey building. Do NOT transcribe any text and do NOT name the building. "
        'Return JSON {"plausible": true|false, "confidence": 0..1, "issues": ["short", ...], "note": "one sentence"}.'
    )
    out = _post([{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}},
    ]}])
    if out is None:
        return {"available": False}
    return {
        "available": True,
        "model": llm_chat.model_name(),
        "plausible": bool(out.get("plausible")),
        "confidence": out.get("confidence"),
        "issues": [_clean(x) for x in (out.get("issues") or []) if x][:4],
        "note": _clean(out.get("note") or ""),
        "vertices": n_vertices,
    }


def supervise_selection(payload: dict) -> dict:
    """Second-opinion review of the structure-selection optimization."""

    if not llm_chat.llm_available():
        return {"available": False}
    bank = payload.get("bank", {})
    twin = payload.get("twin", {})
    sel = payload.get("selection", {})
    metrics = twin.get("metrics", {})
    context = {
        "benchmarked_structures": [
            {"model": r.get("model"), "n_parameters": r.get("n_parameters"),
             "val_rmse_c": r.get("val_rmse"), "admissible": r.get("admissible")}
            for r in bank.get("rows", [])
        ],
        "operating_twin": twin.get("structure_label"),
        "twin_validation_rmse_c": (metrics.get("validation_rmse") or {}).get("value"),
        "twin_test_rmse_c": (metrics.get("test_rmse") or {}).get("value"),
        "automated_pick": (sel.get("bank_auto_pick") or {}).get("model"),
        "automated_pick_rule": (sel.get("bank_auto_pick") or {}).get("rule"),
        "notes": sel.get("explainer"),
    }
    prompt = (
        "You supervise a model-selection optimization for an RC (resistance-capacitance) thermal identification. "
        "Below are the benchmarked structures with their validation error and admissibility, the automated pick, "
        "and the operating twin chosen. Evaluate the optimization: is the selection sound? Flag red flags "
        "(over-parameterised structures reaching suspiciously low error = degeneracy/overfit; near-ties between "
        "structures; sensitivity to initialization; a physically implausible winner). Do you agree with the "
        "operating twin? Ground STRICTLY in the numbers provided; never invent a value. "
        'Return JSON {"agrees_with_twin": true|false, "confidence": 0..1, "assessment": "2-3 sentences", '
        '"concerns": ["short", ...]}.\n\nCONTEXT:\n' + json.dumps(context, ensure_ascii=False)
    )
    out = _post([{"role": "user", "content": prompt}])
    if out is None:
        return {"available": False}
    return {
        "available": True,
        "model": llm_chat.model_name(),
        "agrees_with_twin": bool(out.get("agrees_with_twin")),
        "confidence": out.get("confidence"),
        "assessment": (out.get("assessment") or "").strip(),
        "concerns": [x for x in (out.get("concerns") or []) if x][:4],
    }
