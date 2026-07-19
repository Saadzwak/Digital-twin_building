"""Run a resumable, deterministic M4 multi-start shard one label at a time."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from thermal_twin.multistart import MultiStartConfig, run_multistart_shard, write_shard
from thermal_twin.topologies import reference_model_bank


def _indices(value: str) -> list[int]:
    values = [int(item) for item in value.split(",") if item.strip()]
    if not values or len(values) != len(set(values)):
        raise argparse.ArgumentTypeError("indices must be a non-empty list without duplicates")
    return values


def _load_or_empty(path: Path, config: MultiStartConfig) -> dict[str, object]:
    if not path.is_file():
        return {"config": vars(config), "model_indices": [], "outcomes": [], "selected": [], "basin_summaries": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("config") != vars(config):
        raise ValueError("Existing shard uses a different frozen multi-start configuration.")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--indices", type=_indices, required=True)
    parser.add_argument("--shard", required=True)
    arguments = parser.parse_args()
    root = arguments.project_root.resolve()
    path = root / "runs" / "m4" / "multistart" / "shards" / f"{arguments.shard}.json"
    config = MultiStartConfig()
    payload = _load_or_empty(path, config)
    completed = set(payload["model_indices"])
    requested = set(arguments.indices)
    unexpected = completed - requested
    if unexpected:
        raise ValueError(f"Existing shard contains labels not requested now: {sorted(unexpected)}")
    hourly = pd.read_csv(root / "data" / "processed" / "hourly_reference.csv", parse_dates=["Date"]).set_index("Date")
    bank = reference_model_bank()
    for index in arguments.indices:
        if index in completed:
            print(f"model_index={index} status=already_checkpointed")
            continue
        piece = run_multistart_shard(hourly, [index], config)
        payload["model_indices"].extend(piece["model_indices"])
        payload["outcomes"].extend(piece["outcomes"])
        payload["selected"].extend(piece["selected"])
        payload["basin_summaries"].extend(piece["basin_summaries"])
        write_shard(path, payload)
        completed.add(index)
        print(f"model_index={index} model={bank[index].name} attempts={config.n_starts} status=checkpointed")
    print(f"shard={arguments.shard} total_attempts={len(payload['outcomes'])} path={path}")


if __name__ == "__main__":
    main()
