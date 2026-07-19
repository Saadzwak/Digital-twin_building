"""M10 chat constrained to the executed M4/M5/M9 evidence cards."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Literal
import unicodedata

from .dashboard_contract import IntervalEstimate, load_dashboard_payload
from .validation_gate import M4ValidationError, initialization_sensitive, require_validated_m4


Intent = Literal[
    "model_status", "topology", "metrics", "residual_episode", "scenario", "out_of_scope", "unsupported"
]


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
    "mur", "wall", "facade", "paroi", "vitrage", "window", "economie", "savings", "prix", "tarif", "cause", "causal",
)


def _normalized(text: str) -> str:
    return "".join(
        character for character in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(character)
    )


def classify_intent(query: str) -> Intent:
    normalized = _normalized(query)
    if any(pattern in normalized for pattern in OUT_OF_SCOPE_PATTERNS):
        return "out_of_scope"
    if any(word in normalized for word in ("topologie", "structure", "modele")):
        return "topology"
    if any(word in normalized for word in ("rmse", "bic", "metrique", "classement")):
        return "metrics"
    if any(word in normalized for word in ("residu", "derive", "rupture")):
        return "residual_episode"
    if any(word in normalized for word in ("scenario", "contrefactuel", "intervention", "hvac")):
        return "scenario"
    if any(word in normalized for word in ("etat", "statut", "convergence", "confiance", "initialisation")):
        return "model_status"
    return "unsupported"


def _out_of_scope_card() -> AnswerCard:
    return AnswerCard(
        kind="refusal",
        text="Je ne peux pas identifier indépendamment un mur, une façade, un vitrage, une cause ou une économie réelle avec ces données.",
        run_source=None,
        scope_note="Les branches RC sont effectives; les demandes causales, par paroi et d’économie sont hors périmètre.",
    )


def _unsupported_card() -> AnswerCard:
    return AnswerCard(
        kind="refusal",
        text="Je n’ai pas de carte de preuve sourcée pour cette demande dans le périmètre identifié.",
        run_source=None,
        scope_note="Le chat répond seulement sur l’état, la structure, les métriques, le résidu et les scénarios conditionnels disponibles.",
    )


def _blocked_card(error: Exception) -> AnswerCard:
    return AnswerCard(
        kind="blocked",
        text="Je ne peux pas répondre depuis les paramètres identifiés : la reproduction M4 n’est pas validée ou ses artefacts sont absents.",
        run_source=None,
        scope_note=str(error),
    )


def _load_context(project_root: Path | str) -> dict[str, object]:
    path = Path(project_root).resolve() / "runs" / "m10" / "chat_context.json"
    if not path.is_file():
        raise FileNotFoundError("Validated chat context is absent; no fallback answer is allowed.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload.get("run_source"):
        raise ValueError("Malformed validated chat context.")
    return payload


def write_chat_context(project_root: Path | str) -> Path:
    """Materialize fixed answer cards from the M9 payload, never free text facts."""

    root = Path(project_root).resolve()
    verdict = require_validated_m4(root)
    payload = load_dashboard_payload(root)
    residual = payload.dated_drift or payload.identity_metrics[:1]
    caveat = (
        " Identification sensible à l’initialisation : interprétez les plages inter-départs comme une dispersion empirique, non comme un intervalle de confiance statistique."
        if initialization_sensitive(verdict)
        else " La stabilité rapportée concerne uniquement les départs échantillonnés."
    )
    responses = {
        "model_status": {
            "text": "Voici l’état d’identification et les métriques associées.",
            "estimates": [asdict(item) for item in payload.identity_metrics],
            "scope_note": payload.identity_limit,
        },
        "topology": {
            "text": "Voici la structure RC effectivement retenue par le classement BIC de validation.",
            "estimates": [asdict(item) for item in payload.identity_metrics],
            "scope_note": payload.identity_limit,
        },
        "metrics": {
            "text": "Voici les métriques reproduites avec leur plage déclarée.",
            "estimates": [asdict(item) for item in payload.identity_metrics],
            "scope_note": "Le départ est choisi par MSE train; la validation sert au classement entre topologies.",
        },
        "residual_episode": {
            "text": "Voici les éléments de dérive ou, en leur absence, la métrique résiduelle disponible.",
            "estimates": [asdict(item) for item in residual],
            "scope_note": "Les ruptures sont des signaux diagnostiques, pas des causes attribuées.",
        },
        "scenario": {
            "text": "Voici les scénarios thermiques conditionnels calculés à partir des paramètres identifiés.",
            "estimates": [asdict(item) for item in payload.conditional_counterfactuals],
            "scope_note": "Ce ne sont ni des économies, ni une recommandation d’intervention physique.",
        },
    }
    for response in responses.values():
        response["text"] += caveat
    context = {
        "run_source": payload.run_source,
        "m4_validation_route": verdict.get("validation_route", verdict.get("verdict")),
        "initialization_caveat": caveat.strip(),
        "responses": responses,
        "scope": "Only dashboard IntervalEstimate cards from validated M4/M5/M9 artifacts are eligible.",
    }
    directory = root / "runs" / "m10"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "chat_context.json"
    path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def answer(query: str, project_root: Path | str) -> AnswerCard:
    """Serve an allowlisted sourced card or an explicit scope refusal."""

    intent = classify_intent(query)
    if intent == "out_of_scope":
        return _out_of_scope_card()
    if intent == "unsupported":
        return _unsupported_card()
    try:
        require_validated_m4(project_root)
        context = _load_context(project_root)
    except (M4ValidationError, FileNotFoundError, ValueError) as error:
        return _blocked_card(error)
    responses = context.get("responses")
    if not isinstance(responses, dict) or intent not in responses:
        return _unsupported_card()
    content = responses[intent]
    if not isinstance(content, dict):
        return _unsupported_card()
    estimates = tuple(IntervalEstimate(**item) for item in content.get("estimates", []))
    return AnswerCard(
        kind="answer",
        text=str(content["text"]),
        run_source=str(context["run_source"]),
        estimates=estimates,
        scope_note=str(content.get("scope_note", "Only identified-model evidence is used.")),
    )


def serialize_card(card: AnswerCard) -> dict[str, object]:
    return asdict(card)
