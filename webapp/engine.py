"""Backend orchestration for the control-room web app.

Reuses the validated compute modules unchanged. Records one real reference run
(bank + drift + scenarios) and journals both the ordered event stream and the
product payload, so the live view can *replay a real computation* at an
accelerated cadence — the honest fast path sanctioned when the fully live bank
is too slow for a demo. Uploaded data always runs live (no reference exists).
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Iterator

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thermal_twin.live_run import DemoConfig, load_product_payload, run_live_pipeline  # noqa: E402
from thermal_twin.sanitize import clean  # noqa: E402
from thermal_twin.topologies import reference_model_bank  # noqa: E402

REFERENCE_STARTS = 3  # stable pick already at 3 (train-MSE rule is deterministic); kept snappy for replay


def topology_graph(topology) -> dict:
    """Serializable RC graph for the schematic renderer."""

    nodes = []
    for index, name in enumerate(topology.node_names):
        nodes.append({"id": index, "name": name, "kind": "air" if index == 0 else "mass"})
    resistances = []
    for left, right, r_index in topology.edges:
        resistances.append({"id": int(r_index), "from": int(left), "to": int(right)})
    for node, r_index in topology.outdoor_edges:
        resistances.append({"id": int(r_index), "from": int(node), "to": "outdoor"})
    capacities = [{"node": index} for index in range(topology.n_nodes)]
    return {
        "name": topology.name,
        "n_parameters": topology.n_resistances + topology.n_capacitances + 1,
        "duplicate_of": topology.duplicate_of,
        "nodes": nodes,
        "resistances": resistances,
        "capacities": capacities,
        "injection_node": 0,
        "measurement_node": 0,
    }


def all_topology_graphs() -> dict:
    return {topo.name: topology_graph(topo) for topo in reference_model_bank()}


def _events_path(root: Path, name: str) -> Path:
    return root / "runs" / "demo" / name / "live_events.json"


def record_reference(root: Path | str, force: bool = False) -> dict:
    """Run one real reference pipeline and journal events + payload. Idempotent."""

    root = Path(root).resolve()
    events_path = _events_path(root, "reference")
    payload = load_product_payload(root, journal_name="reference")
    if payload is not None and events_path.is_file() and not force:
        return {"cached": True, "payload": payload}

    config = DemoConfig(n_starts=REFERENCE_STARTS, journal_name="reference")
    events: list[dict] = []
    start = time.perf_counter()
    generator = run_live_pipeline(root, config)
    final = None
    try:
        while True:
            event = next(generator)
            events.append({"t": round(time.perf_counter() - start, 3), "event": _scrub(clean(event))})
    except StopIteration as stop:
        final = stop.value
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
    return {"cached": False, "payload": clean(final)}


def _scrub(event: dict) -> dict:
    """Drop source-file identifiers and local paths that should never reach the wire."""

    if not isinstance(event, dict):
        return event
    if event.get("kind") == "plan":
        event = {k: v for k, v in event.items() if k not in ("filename", "preview_path", "level")}
    if event.get("kind") == "payload_ready":
        # on-disk artifact paths are internal — strip them from the wire/journal
        event = {k: v for k, v in event.items() if k != "paths"}
    return event


def replay_reference(root: Path | str, target_seconds: float = 42.0) -> Iterator[dict]:
    """Yield the recorded reference events paced into ~target_seconds (real replay)."""

    root = Path(root).resolve()
    events_path = _events_path(root, "reference")
    if not events_path.is_file():
        record_reference(root)
    records = json.loads(events_path.read_text(encoding="utf-8"))
    if not records:
        return
    real_total = max(r["t"] for r in records) or 1.0
    factor = target_seconds / real_total
    yield {"kind": "mode", "mode": "replay", "real_seconds": round(real_total, 1),
           "note": "Real computation over one year of real hourly measurements."}
    previous = 0.0
    for record in records:
        wait = (record["t"] - previous) * factor
        previous = record["t"]
        if wait > 0:
            time.sleep(min(wait, 1.2))
        yield _scrub(record["event"])


def live_upload(root: Path | str, hourly, provenance) -> Iterator[dict]:
    """Stream the real (non-replay) pipeline for uploaded data."""

    root = Path(root).resolve()
    yield {"kind": "mode", "mode": "live",
           "note": "Live real computation on your uploaded measurements."}
    config = DemoConfig(n_starts=REFERENCE_STARTS, journal_name="upload")
    generator = run_live_pipeline(root, config, uploaded_hourly=hourly, upload_provenance=provenance)
    try:
        while True:
            yield _scrub(clean(next(generator)))
    except StopIteration:
        return
