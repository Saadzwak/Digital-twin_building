"""Single gate preventing unvalidated M4 output from feeding product claims."""

from __future__ import annotations

import json
from pathlib import Path


class M4ValidationError(RuntimeError):
    """Raised when a downstream product path attempts to use an invalid M4 run."""


def load_m4_verdict(project_root: Path | str) -> dict[str, object]:
    path = Path(project_root).resolve() / "runs" / "m4" / "verdict.json"
    if not path.is_file():
        raise M4ValidationError(f"M4 verdict is absent: {path}")
    try:
        verdict = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise M4ValidationError(f"M4 verdict cannot be parsed: {path}") from exc
    if not isinstance(verdict, dict):
        raise M4ValidationError("M4 verdict must be a JSON object.")
    return verdict


def require_validated_m4(project_root: Path | str) -> dict[str, object]:
    verdict = load_m4_verdict(project_root)
    if verdict.get("validated") is not True:
        conclusion = verdict.get("conclusion", "unknown")
        raise M4ValidationError(
            "Downstream identified-model claims are blocked because M4 is not validated "
            f"(conclusion={conclusion!r})."
        )
    return verdict
