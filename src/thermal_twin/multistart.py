"""Public M4 multi-start API with artifact-integrity sealing."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
from pathlib import Path

from . import multistart_impl as _implementation


def _quantile(values: Sequence[float], probability: float) -> float | None:
    if len(values) == 0:
        return None
    return float(_implementation.np.quantile(_implementation.np.asarray(values, dtype=float), probability))


_implementation._quantile = _quantile

from .multistart_impl import *  # noqa: F401,F403,E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def write_multistart_artifacts(project_root, merged, oracle, verdict):
    """Persist then seal the exact start artifact consumed by downstream M5–M10."""

    paths = _implementation.write_multistart_artifacts(project_root, merged, oracle, verdict)
    all_starts = Path(paths["all_starts"])
    selected = Path(paths["selected"])
    dispersion = Path(paths["basin_dispersion"])
    verdict_path = Path(paths["verdict"])
    sealed = json.loads(verdict_path.read_text(encoding="utf-8"))
    outcomes = merged["outcomes"]
    sealed["artifact_integrity"] = {
        "all_starts_sha256": _sha256(all_starts),
        "selected_by_train_mse_sha256": _sha256(selected),
        "basin_dispersion_sha256": _sha256(dispersion),
        "outcome_count": len(outcomes),
        "unique_model_start_pairs": len({(row["model_index"], row["start_id"]) for row in outcomes}),
        "config": merged["config"],
    }
    temporary = verdict_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(sealed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(verdict_path)
    return paths
