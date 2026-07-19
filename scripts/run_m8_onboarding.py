"""Write the current five-question-or-fewer onboarding contract."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thermal_twin.onboarding import OnboardingState, write_onboarding_contract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    print(write_onboarding_contract(arguments.project_root, OnboardingState()))


if __name__ == "__main__":
    main()
