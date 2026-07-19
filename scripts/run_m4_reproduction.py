"""Run the complete immutable 19-model M4 reproduction and journal every row."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from thermal_twin.reproduction import primary_validation, run_reproduction, write_reproduction_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    root = arguments.project_root.resolve()
    hourly = pd.read_csv(root / "data" / "processed" / "hourly_reference.csv", parse_dates=["Date"]).set_index("Date")
    rows, fits, validation = run_reproduction(hourly)
    csv_path, json_path = write_reproduction_artifacts(root, rows, fits, validation)
    for row in rows:
        duplicate = f" duplicate_of={row.duplicate_of}" if row.duplicate_of else ""
        print(
            f"{row.model} success={row.fit_success} VAL_RMSE={row.validation_rmse:.12f} "
            f"VAL_BIC={row.validation_bic:.12f} TEST_RMSE={row.test_rmse:.12f}{duplicate}"
        )
    print(f"primary_validation={primary_validation(rows)}")
    print(f"wrote={csv_path}")
    print(f"wrote={json_path}")


if __name__ == "__main__":
    main()
