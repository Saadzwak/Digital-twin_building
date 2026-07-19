"""Exercise the product UI headlessly: landing, onboarding, dashboard, chat.

The full live pipeline is exercised by the engine tests and the manual
browser journey; this smoke keeps to what AppTest can cover quickly using
the journaled run.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thermal_twin.live_run import load_product_payload
from thermal_twin.product_chat import product_answer


def _disable_app_test_finalizer() -> None:
    """Avoid a Windows restricted-token cleanup traceback after a passing AppTest."""

    def no_cleanup(*arguments: object, **keywords: object) -> None:
        del arguments, keywords

    tempfile.TemporaryDirectory._cleanup = classmethod(no_cleanup)


def _click(app, label: str):
    for button in app.button:
        if button.label == label:
            return button.click()
    raise RuntimeError(f"Button {label!r} not found; labels: {[b.label for b in app.button]}")


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

    if load_product_payload(root) is None:
        raise RuntimeError("No journaled live run; execute the demo once before the smoke.")

    # Landing page.
    app = AppTest.from_file(str(root / "dashboard" / "app.py"))
    app.run(timeout=60)
    if app.exception:
        raise RuntimeError("Landing exception: " + "; ".join(item.value for item in app.exception))
    labels = [button.label for button in app.button]
    if "Essayer avec le bâtiment Pleiades" not in labels:
        raise RuntimeError(f"Demo button missing on landing; buttons: {labels}")
    print("landing=ok")

    # Dashboard: onboarding gate first.
    app = AppTest.from_file(str(root / "dashboard" / "app.py"))
    app.session_state["page"] = "tableau"
    app.run(timeout=60)
    if app.exception:
        raise RuntimeError("Onboarding exception: " + "; ".join(item.value for item in app.exception))
    if not app.radio:
        raise RuntimeError("Onboarding questions did not render.")
    n_questions = len(app.radio)
    _click(app, "Valider et ouvrir le tableau de bord")
    app.run(timeout=60)
    if app.exception:
        raise RuntimeError("Dashboard exception: " + "; ".join(item.value for item in app.exception))
    rendered_headers = [item.value for item in app.header] + [item.value for item in app.title]
    required = (
        "Diagnostic thermique du bâtiment",
        "Quand votre bâtiment change de comportement",
        "Ce que le modèle a identifié",
        "Scénarios d'intervention (simulation conditionnelle)",
        "Interroger le diagnostic",
    )
    missing = [title for title in required if title not in rendered_headers]
    if missing:
        raise RuntimeError(f"Dashboard sections missing: {missing}; got {rendered_headers}")
    warnings = " ".join(str(item.value) for item in app.warning)
    if "Fiabilité du diagnostic" not in warnings:
        raise RuntimeError("The permanent reliability banner is missing.")
    print(f"onboarding_questions={n_questions}")
    print("dashboard_sections=ok")

    # Chat through the UI.
    app.text_input[0].set_value("Quand le bâtiment décroche-t-il ?")
    _click(app, "Poser la question")
    app.run(timeout=60)
    if app.exception:
        raise RuntimeError("Chat exception: " + "; ".join(item.value for item in app.exception))
    if not app.success:
        raise RuntimeError("Chat did not render a sourced answer for an in-scope question.")
    print("chat_in_scope=answer")

    # Chat scope checks through the API (same code path as the UI).
    refused = product_answer("Quelle est la perte du mur nord ?", root)
    unknown = product_answer("Raconte-moi une blague", root)
    if refused.kind != "refusal" or not refused.alternative_text:
        raise RuntimeError("Wall question must be refused with a served alternative.")
    if unknown.kind != "refusal":
        raise RuntimeError("Unrelated question must be refused.")
    print("chat_wall=refusal_with_alternative")
    print("chat_unrelated=refusal")


if __name__ == "__main__":
    main()
