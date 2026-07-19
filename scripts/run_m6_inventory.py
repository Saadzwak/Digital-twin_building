"""Render and inventory supplied plans; emit only human-reviewable geometry state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thermal_twin.geometry import inventory_plans, write_geometry_review_request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    root = arguments.project_root.resolve()
    inventory = inventory_plans(root, root / "tmp" / "m6_previews")
    review_path = write_geometry_review_request(root, inventory)
    print(json.dumps([record.__dict__ for record in inventory], ensure_ascii=False, indent=2))
    print(f"review_request={review_path}")


if __name__ == "__main__":
    main()
