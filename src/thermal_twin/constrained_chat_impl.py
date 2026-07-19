"""Deterministic M10 chat: only sourced, scoped and uncertainty-bearing answers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Literal

from .dashboard_contract import IntervalEstimate
from .validation_gate import M4ValidationError, require_validated_m4


Intent = Literal["model_status", "topology", "metrics", "residual_episode", "scenario", "out_of_scope"]


@dataclass(frozen=True)
class AnswerCard:
    kind: Literal["answer", "refusal", "blocked"]
    text: str
    run_source: str | None
    estimates: tuple[IntervalEstimate, ...] = ()
    scope_note: str | None = None

    def __post_init__(self) -> None:
        if self.kind == "answer" and not self.run_source:
            raise ValueError("A substantive answer requires a validated run source.")
        if self.kind != "answer" and self.estimates:
            raise ValueError("Refusal and blocked cards cannot expose unsourced estimates.")


OUT_OF_SCOPE_PATTERNS = (
    "mur", "wall", "façade", "facade", "paroi", "vitrage", "window",
    "économie", "economie", "savings", "prix", "tarif", "cause", "causal",
)


def classify_intent(query: str) -> Intent:
    normalized = query.lower()
    if any(pattern in normalized for pattern in OUT_OF_SCOPE_PATTERNS):
        return "out_of_scope"
    if any(word in normalized for word in ("topologie", "structure", "modèle", "modele")):
        return "topology"
    if any(word in normalized for word in ("rmse", "bic", "métrique", "metrique", "classement")):
        return "metrics"
    if any(word in normalized for word in ("résidu", "residu", "dérive", "derive", "rupture")):
        return "residual_episode"
    if any(word in normalized for word in ("scénario", "scenario", "contrefactuel", "intervention")):
        return "scenario"
    return "model_status"


def _out_of_scope_card() -> AnswerCard:
    return AnswerCard(
        kind="refusal",
        text=(
            "Je ne peux pas identifier indépendamment un mur, une façade, un vitrage, "
            "une cause ou une économie réelle avec ces données."
        ),
        run_source=None,
        scope_note="Les chemins RC sont effectifs; les demandes causales, par paroi et d’économie sont hors périmètre.",
    )


def _blocked_card(error: Exception) -> AnswerCard:
    return AnswerCard(
        kind="blocked",
        text="Je ne peux pas répondre depuis les paramètres identifiés : la reproduction M4 n’est pas validée.",
        run_source=None,
        scope_note=str(error),
    )


def _load_context(project_root: Path | str) -> dict[str, object]:
    path = Path(project_root).resolve() / "runs" / "m10" / "chat_context.json"
    if not path.is_file():
        raise FileNotFoundError("Validated chat context is absent; no fallback answer is allowed.")
    return json.loads(path.read_text(encoding="utf-8"))


def answer(query: str, project_root: Path | str) -> AnswerCard:
    """Answer a small allowlist from a validated context, otherwise refuse/block."""

    intent = classify_intent(query)
    if intent == "out_of_scope":
        return _out_of_scope_card()
    try:
        require_validated_m4(project_root)
        context = _load_context(project_root)
    except (M4ValidationError, FileNotFoundError) as error:
        return _blocked_card(error)
    run_source = str(context["run_source"])
    responses = context.get("responses", {})
    if not isinstance(responses, dict) or intent not in responses:
        return AnswerCard(
            kind="refusal",
            text="Je ne dispose pas d’une carte sourcée pour cette demande dans le périmètre identifié.",
            run_source=None,
        )
    content = responses[intent]
    if not isinstance(content, dict):
        raise ValueError("Malformed validated chat context.")
    estimates = tuple(IntervalEstimate(**item) for item in content.get("estimates", []))
    return AnswerCard(
        kind="answer",
        text=str(content["text"]),
        run_source=run_source,
        estimates=estimates,
        scope_note=str(content.get("scope_note", "Only identified-model evidence is used.")),
    )


def serialize_card(card: AnswerCard) -> dict[str, object]:
    return asdict(card)
