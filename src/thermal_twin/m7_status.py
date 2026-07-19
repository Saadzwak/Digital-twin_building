"""Materialize the honest M7 state while geometry awaits human acceptance."""

from __future__ import annotations

import json
from pathlib import Path

from .validation_gate import require_validated_m4


def materialize_m7_status(project_root: Path | str) -> dict[str, object]:
    root = Path(project_root).resolve()
    verdict = require_validated_m4(root)
    review = root / "runs" / "m6" / "geometry_review_request.json"
    status = {
        "m4_validation_route": verdict.get("validation_route", verdict.get("verdict")),
        "status": "HUMAN_GEOMETRY_VALIDATION_REQUIRED",
        "fit_executed": False,
        "reason": "No plan boundary/scale/north/height has been accepted by a human reviewer.",
        "constraint_when_ready": "R_i = r'' / A_i; one shared r'' remains a free identified parameter across known surface areas.",
        "identifiability_limit": "With shared outdoor forcing, individual facade losses are not independently identified.",
        "geometry_review_source": str(review),
    }
    directory = root / "runs" / "m7"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status
