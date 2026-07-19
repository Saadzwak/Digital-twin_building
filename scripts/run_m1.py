"""Run M1 with the same memory-bounded protocol used for the executed artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thermal_twin.ingestion import prepare_reference_dataset, split_reference_months, write_prepared_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    prepared = prepare_reference_dataset(arguments.project_root)
    splits = split_reference_months(prepared.hourly)
    csv_path, manifest_path = write_prepared_dataset(prepared, arguments.project_root)
    print(f"hourly_rows={len(prepared.hourly)}")
    print("splits=" + ", ".join(f"{name}={len(part)}" for name, part in splits.items()))
    print(f"wrote={csv_path}")
    print(f"manifest={manifest_path}")


if __name__ == "__main__":
    main()
