"""Execute the real post-M4 modules after an A/B multi-start verdict."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thermal_twin.constrained_chat import write_chat_context
from thermal_twin.dashboard_materialize import materialize_dashboard_payload
from thermal_twin.diagnostics import run_validated_real_diagnostics
from thermal_twin.geometry import inventory_plans, write_geometry_review_request
from thermal_twin.m7_status import materialize_m7_status
from thermal_twin.onboarding import OnboardingState, write_onboarding_contract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    root = arguments.project_root.resolve()
    diagnostics = run_validated_real_diagnostics(root)
    inventory = inventory_plans(root, root / "tmp" / "m6_previews")
    geometry = write_geometry_review_request(root, inventory)
    m7 = materialize_m7_status(root)
    onboarding = write_onboarding_contract(root, OnboardingState())
    dashboard = materialize_dashboard_payload(root)
    chat = write_chat_context(root)
    print(f"m5={root / 'runs' / 'm5' / 'diagnostic.json'}")
    print(f"m5_topology={diagnostics['topology_label']}")
    print(f"m6={geometry}")
    print(f"m7_status={m7['status']}")
    print(f"m8={onboarding}")
    print(f"m9={root / 'runs' / 'm9' / 'dashboard_payload.json'}")
    print(f"m9_topology={dashboard.topology_label}")
    print(f"m10={chat}")


if __name__ == "__main__":
    main()
