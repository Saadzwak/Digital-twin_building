"""Execute the frozen M1 reference preparation on real PLEIAData."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thermal_twin.reference_ingestion import (
    prepare_reference_dataset,
    split_reference_months,
    write_reference_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    prepared = prepare_reference_dataset(arguments.project_root)
    splits = split_reference_months(prepared.hourly)
    output, manifest = write_reference_dataset(prepared, arguments.project_root)
    print(f"source={prepared.source_paths.root}")
    print(f"archive_sha256={prepared.source_paths.archive_sha256}")
    print(f"sensor_count={prepared.sensor_count}")
    print(f"selected_sensor_observations={prepared.selected_sensor_observations}")
    print(f"unique_tin_timestamps={prepared.unique_tin_timestamps}")
    print(f"meter_id={prepared.meter_id}")
    print(f"energy_interval_seconds={prepared.energy_interval_seconds:.6f}")
    print(f"q_clip_w=[{prepared.q_clip_lower_w:.12f}, {prepared.q_clip_upper_w:.12f}]")
    print(f"hourly_rows={len(prepared.hourly)}")
    print(f"range_utc={prepared.hourly.index.min()} -> {prepared.hourly.index.max()}")
    print("splits=" + ", ".join(f"{name}={len(part)}" for name, part in splits.items()))
    print(f"wrote={output}")
    print(f"manifest={manifest}")


if __name__ == "__main__":
    main()
