"""Control-room web app server (FastAPI). Serves the SPA and the sanitized API.

Every JSON response passes through ``sanitize.clean`` so no NaN/Inf can reach the
client — the "Infinite extent" class of render errors cannot occur.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thermal_twin.building_geometry import load_massing, write_massing  # noqa: E402
from thermal_twin.building_3d import build_and_cache, load_buildings  # noqa: E402
from thermal_twin.live_run import load_product_payload, load_drift_daily, prepare_uploaded_csv  # noqa: E402
from thermal_twin.product_chat import product_answer, serialize_product_card  # noqa: E402
from thermal_twin import llm_chat  # noqa: E402
from thermal_twin import llm_supervisor  # noqa: E402
from thermal_twin.renovation import renovation_report, interpretation  # noqa: E402
from thermal_twin.sanitize import clean  # noqa: E402

import engine  # noqa: E402  (webapp/engine.py, same directory)

STATIC = Path(__file__).resolve().parent / "static"
app = FastAPI(title="Thermal Twin — control room", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def _no_store(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


def _ndjson(generator) -> StreamingResponse:
    def stream():
        for event in generator:
            yield json.dumps(clean(event), ensure_ascii=False) + "\n"
    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.on_event("startup")
def _startup() -> None:
    if load_massing(ROOT) is None:
        write_massing(ROOT)
    # Ensure the real 3D footprints are cached so the map never blocks on network.
    if load_buildings(ROOT) is None:
        try:
            build_and_cache(ROOT)
        except Exception:  # noqa: BLE001 - the map falls back to static if absent
            pass
    # Precompute the reference bank once so the live view is a fast real replay.
    engine.record_reference(ROOT)
    # Announce the chat backend clearly (real LLM vs deterministic fallback).
    if llm_chat.llm_available():
        print(f"[chat] OpenAI LLM enabled — model {llm_chat.model_name()}", flush=True)
    else:
        print("[chat] OPENAI_API_KEY not set — chat falls back to the deterministic guide", flush=True)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/geometry")
def geometry() -> JSONResponse:
    return JSONResponse(clean(load_massing(ROOT) or {}))


@app.get("/api/buildings-3d")
def buildings_3d() -> JSONResponse:
    """Real BD TOPO footprints (target + urban neighbours) for the 3D map.

    Served from the on-disk cache so the demo never blocks on the network. If the
    cache is somehow missing, try to build it once; on failure return an empty set
    and the client keeps its abstract massing rather than a cube.
    """
    data = load_buildings(ROOT)
    if data is None:
        try:
            data = build_and_cache(ROOT)
        except Exception:  # noqa: BLE001 - never let the map endpoint 500
            data = {"source": "none", "buildings": []}
    return JSONResponse(clean(data or {"source": "none", "buildings": []}))


@app.get("/api/topologies")
def topologies() -> JSONResponse:
    return JSONResponse(clean(engine.all_topology_graphs()))


@app.post("/api/run/reference")
def run_reference() -> StreamingResponse:
    return _ndjson(engine.replay_reference(ROOT))


@app.post("/api/run/upload")
async def run_upload(file: UploadFile = File(...)) -> StreamingResponse:
    content = await file.read()
    try:
        hourly, provenance = prepare_uploaded_csv(content)
    except (ValueError, Exception) as error:  # noqa: BLE001 - surface any parse failure to the client
        message = str(error) or "CSV illisible."

        def err():
            yield {"kind": "error", "message": message}
        return _ndjson(err())
    return _ndjson(engine.live_upload(ROOT, hourly, provenance))


@app.get("/api/payload")
def payload(source: str = "reference") -> JSONResponse:
    name = "upload" if source == "upload" else "reference"
    data = load_product_payload(ROOT, journal_name=name)
    if data is None:
        data = load_product_payload(ROOT, journal_name="reference")
    return JSONResponse(clean(data or {}))


@app.get("/api/drift")
def drift(source: str = "reference") -> JSONResponse:
    name = "upload" if source == "upload" else "reference"
    frame = load_drift_daily(ROOT, journal_name=name)
    if frame is None:
        frame = load_drift_daily(ROOT, journal_name="reference")
    if frame is None:
        return JSONResponse({"daily": []})
    rows = []
    for date, row in frame.iterrows():
        rows.append({
            "date": str(date.date()),
            "measured": row.get("Tin_measured"),
            "expected": row.get("Tin_estimated"),
            "cumulative": row.get("cumulative_gap_c_h"),
        })
    return JSONResponse(clean({"daily": rows}))


@app.get("/api/renovation")
def renovation() -> JSONResponse:
    return JSONResponse(clean(renovation_report(ROOT)))


@app.get("/api/interpretation")
def interpretation_endpoint(source: str = "reference") -> JSONResponse:
    name = "upload" if source == "upload" else "reference"
    payload = load_product_payload(ROOT, journal_name=name) or load_product_payload(ROOT, journal_name="reference")
    if payload is None:
        return JSONResponse({"leads": []})
    hl = payload.get("indicators", {}).get("heat_loss", {})
    share = hl.get("direct_path_share") if hl.get("physically_readable") else None
    switch = payload.get("drift", {}).get("structural_switch")
    response_hours = payload.get("indicators", {}).get("response_time_hours")
    return JSONResponse(clean(interpretation(share, switch, response_hours)))


@app.get("/api/verify-geometry")
def verify_geometry() -> JSONResponse:
    """GPT-5.6 vision QA of the plan-reading step (footprint extraction)."""
    return JSONResponse(clean(llm_supervisor.supervise_geometry(ROOT)))


@app.get("/api/verify-selection")
def verify_selection(source: str = "reference") -> JSONResponse:
    """GPT-5.6 second-opinion review of the structure-selection optimization."""
    name = "upload" if source == "upload" else "reference"
    payload = load_product_payload(ROOT, journal_name=name) or load_product_payload(ROOT, journal_name="reference")
    if payload is None:
        return JSONResponse({"available": False})
    return JSONResponse(clean(llm_supervisor.supervise_selection(payload)))


@app.post("/api/chat")
async def chat(body: dict) -> JSONResponse:
    query = str(body.get("query", ""))
    source = body.get("source", "reference")
    journal = "upload" if source == "upload" else "reference"
    # The deterministic guide is always computed: it is the fallback, and it is the
    # source of the payload-derived estimates rendered under the answer.
    card = serialize_product_card(product_answer(query, ROOT, journal_name=journal))
    card["engine"] = "deterministic"

    # Prefer a real LLM answer when a key is configured. It understands
    # reformulations and unanticipated questions; it is grounded on the full
    # computed payload and forbidden from inventing numbers. On any failure we
    # keep the deterministic card. The numeric estimates always stay payload-sourced.
    if card["kind"] != "blocked" and llm_chat.llm_available():
        payload = load_product_payload(ROOT, journal_name=journal) or load_product_payload(ROOT, journal_name="reference")
        if payload is not None:
            reno = renovation_report(ROOT)
            llm = llm_chat.answer_llm(query, payload, reno)
            if llm is not None:
                det_estimates = card.get("estimates") or []
                det_answered = card["kind"] == "answer"
                card["engine"] = "llm"
                card["text"] = llm["text"]
                card["kind"] = llm["kind"]
                card["run_source"] = card.get("run_source") or str(payload.get("run_source"))
                card["scope_note"] = llm.get("source") or card.get("scope_note")
                if llm["kind"] == "answer":
                    # keep payload-sourced estimates when the deterministic engine
                    # recognised the same topic; never fabricate a tracer
                    card["estimates"] = det_estimates if det_answered else []
                    card["alternative_text"] = None
                    card["alternative_estimates"] = []
                else:  # refusal — no direct estimates; offer the payload-backed alternative
                    card["estimates"] = []
                    card["alternative_text"] = llm.get("alternative_text") or card.get("alternative_text")
                    if not card.get("alternative_estimates") and det_answered:
                        card["alternative_estimates"] = det_estimates
    return JSONResponse(clean(card))


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
