"""Execute representative constrained-chat requests against the current artifact state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thermal_twin.constrained_chat import answer, serialize_card


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    queries = ["Quel est le RMSE ?", "Quelle perte a le mur nord ?", "Montre la topologie."]
    cards = [serialize_card(answer(query, arguments.project_root)) for query in queries]
    print(json.dumps(cards, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
