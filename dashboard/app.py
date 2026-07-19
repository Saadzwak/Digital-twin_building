"""Entrypoint for the owner-facing thermal diagnostic product."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thermal_twin.product_ui import render

render(Path(__file__).resolve().parents[1])
