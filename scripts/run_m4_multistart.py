"""Execute or merge deterministic uniform multi-start M4 shards."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from thermal_twin.multistart import (
    MultiStartConfig,
    load_shards,
    notebook_parameter_oracle,
    revised_verdict,
    run_multistart_shard,
    write_multistart_artifacts,
    write_shard,
)


def _indices(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--indices", type=_indices)
    parser.add_argument("--shard", type=str)
    parser.add_argument("--aggregate", action="store_true")
    arguments = parser.parse_args()
    root = arguments.project_root.resolve()
    shard_dir = root / "runs" / "m4" / "multistart" / "shards"
    if arguments.aggregate:
        paths = sorted(shard_dir.glob("*.json"))
        merged = load_shards(paths)
        hourly = pd.read_csv(root / "data" / "processed" / "hourly_reference.csv", parse_dates=["Date"]).set_index("Date")
        oracle = notebook_parameter_oracle(hourly)
        verdict = revised_verdict(merged, oracle)
        paths_out = write_multistart_artifacts(root, merged, oracle, verdict)
        print(f"verdict={verdict['verdict']} validated={verdict['validated']}")
        for name, path in paths_out.items():
            print(f"{name}={path}")
        return
    if arguments.indices is None or not arguments.shard:
        parser.error("Execution requires --indices and --shard, or use --aggregate.")
    hourly = pd.read_csv(root / "data" / "processed" / "hourly_reference.csv", parse_dates=["Date"]).set_index("Date")
    config = MultiStartConfig()
    shard = run_multistart_shard(hourly, arguments.indices, config)
    path = write_shard(shard_dir / f"{arguments.shard}.json", shard)
    print(f"shard={arguments.shard} starts={len(shard['outcomes'])} wrote={path}")


if __name__ == "__main__":
    main()
