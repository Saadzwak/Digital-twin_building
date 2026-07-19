"""Machine gate for downstream claims from a reproducible M4 run."""

from __future__ import annotations

import json
from pathlib import Path


class M4ValidationError(RuntimeError):
    """Raised when a downstream product path attempts an invalid M4 claim."""


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
    """Accept only an explicit A/B multi-start verdict, never a bare boolean."""

    verdict = load_m4_verdict(project_root)
    if verdict.get("validated") is not True:
        conclusion = verdict.get("conclusion", "unknown")
        raise M4ValidationError(
            "Downstream identified-model claims are blocked because M4 is not validated "
            f"(conclusion={conclusion!r})."
        )
    route = verdict.get("validation_route", verdict.get("verdict"))
    if route not in {"A", "B"}:
        raise M4ValidationError("Validated M4 verdict lacks an explicit A/B multi-start validation route.")
    if verdict.get("protocol") != "uniform_multistart_notebook_cell_55":
        raise M4ValidationError("Validated M4 verdict does not identify the frozen uniform multi-start protocol.")
    config = verdict.get("config")
    if not isinstance(config, dict) or int(config.get("n_starts", 0)) < 2:
        raise M4ValidationError("Validated M4 verdict lacks a common logged multi-start count.")
    if route == "A" and not isinstance(verdict.get("criterion_a"), dict) or route == "A" and verdict["criterion_a"].get("passed") is not True:
        raise M4ValidationError("Route A requires a recorded strong 4R3C validation-BIC ranking.")
    if route == "B":
        criterion_b = verdict.get("criterion_b")
        if not isinstance(criterion_b, dict) or criterion_b.get("passed") is not True:
            raise M4ValidationError("Route B requires recorded oracle, uniformity and dispersion evidence.")
        if verdict.get("sensitivity_banner_required") is not True:
            raise M4ValidationError("Route B must propagate the initialization-sensitivity warning.")
    return verdict


def initialization_sensitive(verdict: dict[str, object]) -> bool:
    """Whether the permanent product caveat is mandatory for this run."""

    return verdict.get("validation_route", verdict.get("verdict")) == "B"
