"""Exercise the rendered Streamlit sections and constrained chat after M4 A/B."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thermal_twin.constrained_chat import answer


def _disable_app_test_finalizer() -> None:
    """Avoid a Windows restricted-token cleanup traceback after a passing AppTest.

    Streamlit's temporary finalizer reaches a directory that the test sandbox
    cannot enumerate during interpreter shutdown. The test keeps its small
    disposable directories under ``tmp/streamlit_smoke_tmp`` instead; they
    are not dashboard artifacts and are deliberately not used by production.
    """

    def no_cleanup(cls: type[tempfile.TemporaryDirectory], name: str, warn_message: str, ignore_cleanup_errors: bool = False) -> None:
        del cls, name, warn_message, ignore_cleanup_errors

    tempfile.TemporaryDirectory._cleanup = classmethod(no_cleanup)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    root = arguments.project_root.resolve()
    smoke_temp = root / "tmp" / "streamlit_smoke_tmp"
    smoke_temp.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(smoke_temp)
    _disable_app_test_finalizer()
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(root / "dashboard" / "app.py"))
    app.run(timeout=90)
    if app.exception:
        raise RuntimeError("Streamlit AppTest exception: " + "; ".join(item.value for item in app.exception))
    rendered = "\n".join(item.value for item in app.header)
    required = (
        "Identité thermique", "Dispersion des bassins d’initialisation", "Répartition des pertes effectives",
        "Dérive datée du résidu", "Contrefactuels thermiques conditionnels", "Classement des scénarios",
        "Plans et questions d’onboarding", "Chat contraint aux paramètres identifiés",
    )
    missing = [title for title in required if title not in rendered]
    if missing:
        raise RuntimeError(f"Dashboard sections missing from AppTest: {missing}")
    verdict = json.loads((root / "runs" / "m4" / "verdict.json").read_text(encoding="utf-8"))
    route = verdict.get("validation_route", verdict.get("verdict"))
    if route == "B":
        errors = "\n".join(str(item.value) for item in app.error)
        if "sensible à l’initialisation" not in errors:
            raise RuntimeError("Route B requires the permanent initialization-sensitivity dashboard banner.")
    app.text_input[0].set_value("Quel est le RMSE de validation ?")
    app.button[0].click()
    app.run(timeout=90)
    if app.exception:
        raise RuntimeError("Streamlit chat exception: " + "; ".join(item.value for item in app.exception))
    if not app.success:
        raise RuntimeError("Dashboard chat did not render a successful allowed answer.")
    allowed = answer("Quel est le RMSE de validation ?", root)
    rejected = answer("Quelle est la perte du mur nord ?", root)
    unsupported = answer("Raconte-moi une blague", root)
    if allowed.kind != "answer" or rejected.kind != "refusal" or unsupported.kind != "refusal":
        raise RuntimeError("Constrained-chat scope smoke test failed.")
    print("dashboard_sections=8")
    print("initialization_banner=" + ("required_and_rendered" if route == "B" else "not_required"))
    print("chat_allowed=answer")
    print("chat_out_of_scope=refusal")
    print("chat_unknown=refusal")


if __name__ == "__main__":
    main()
