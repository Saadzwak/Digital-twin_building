"""Run the real-data M3 determinism check without changing reference options."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from thermal_twin.identification import evaluate_topology, fit_to_serializable, fit_topology
from thermal_twin.reference_ingestion import split_reference_months
from thermal_twin.topologies import STD_1R1C


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    root = arguments.project_root.resolve()
    hourly = pd.read_csv(root / "data" / "processed" / "hourly_reference.csv", parse_dates=["Date"])
    hourly = hourly.set_index("Date")
    splits = split_reference_months(hourly)
    first = fit_topology(STD_1R1C, splits["train"])
    second = fit_topology(STD_1R1C, splits["train"])
    first_validation = evaluate_topology(first, splits["validation"])
    second_validation = evaluate_topology(second, splits["validation"])
    deterministic = bool((first.parameters_log == second.parameters_log).all()) and first.success == second.success
    run_dir = root / "runs" / "m3"
    run_dir.mkdir(parents=True, exist_ok=True)
    output = run_dir / "determinism_std_1r1c.json"
    payload = {
        "first": fit_to_serializable(first),
        "second": fit_to_serializable(second),
        "first_validation": first_validation.metrics.__dict__,
        "second_validation": second_validation.metrics.__dict__,
        "parameter_vectors_bitwise_equal": deterministic,
    }
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"bitwise_equal={deterministic}")
    print(f"first_success={first.success}; second_success={second.success}")
    print(f"validation_rmse={first_validation.metrics.rmse:.12f}")
    print(f"validation_bic={first_validation.metrics.bic:.12f}")
    print(f"wrote={output}")


if __name__ == "__main__":
    main()
