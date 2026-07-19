"""Five-question maximum onboarding for information unavailable from extraction."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Literal


Answer = Literal["known", "unknown", "not_asked"]


@dataclass(frozen=True)
class OnboardingState:
    thermal_boundary: Answer = "not_asked"
    north_azimuth: Answer = "not_asked"
    floor_heights: Answer = "not_asked"
    glazing_geometry: Answer = "not_asked"
    documented_surface_resistance: Answer = "not_asked"


@dataclass(frozen=True)
class OnboardingQuestion:
    key: str
    prompt: str
    why_needed: str
    enables: tuple[str, ...]


QUESTION_BANK: tuple[OnboardingQuestion, ...] = (
    OnboardingQuestion(
        "thermal_boundary",
        "Quel polygone et quels niveaux correspondent au périmètre thermique mesuré par Tin bloc A ?",
        "Les plans seuls ne relient pas leur géométrie à la moyenne de capteurs du bloc A.",
        ("thermal_boundary",),
    ),
    OnboardingQuestion(
        "north_azimuth",
        "Quel est l’azimut du nord sur le plan ?",
        "L’orientation ne peut pas être déduite de façon fiable des PDFs fournis.",
        ("facade_orientation",),
    ),
    OnboardingQuestion(
        "floor_heights",
        "Quelles hauteurs finies faut-il retenir par niveau du périmètre thermique ?",
        "Le volume et les surfaces de façade nécessitent des hauteurs confirmées.",
        ("volume", "facade_area"),
    ),
    OnboardingQuestion(
        "glazing_geometry",
        "Validez-vous les vitrages tracés et leur hauteur, ou les déclarez-vous inconnus ?",
        "Le ratio vitrage ne peut pas être inféré de contours PDF non validés.",
        ("glazing_ratio",),
    ),
    OnboardingQuestion(
        "documented_surface_resistance",
        "Disposez-vous d’une résistance surfacique effective documentée pour activer la branche géométriquement contrainte ?",
        "Sans cette information, M7 ne doit pas substituer une valeur plausible.",
        ("geometry_constrained_candidate",),
    ),
)


def questions_needed(state: OnboardingState) -> tuple[OnboardingQuestion, ...]:
    """Ask only unresolved facts, in a stable maximum-five priority order."""

    questions = tuple(question for question in QUESTION_BANK if getattr(state, question.key) == "not_asked")
    if len(questions) > 5:
        raise AssertionError("Onboarding must never exceed five questions.")
    return questions


def capabilities(state: OnboardingState) -> dict[str, bool]:
    """Unknown answers disable dependent computations instead of inventing defaults."""

    boundary = state.thermal_boundary == "known"
    north = state.north_azimuth == "known"
    heights = state.floor_heights == "known"
    glazing = state.glazing_geometry == "known"
    surface_resistance = state.documented_surface_resistance == "known"
    return {
        "thermal_boundary": boundary,
        "facade_orientation": boundary and north,
        "facade_area": boundary and north and heights,
        "volume": boundary and heights,
        "glazing_ratio": boundary and north and heights and glazing,
        "geometry_constrained_candidate": boundary and north and heights and surface_resistance,
    }


def write_onboarding_contract(project_root: Path | str, state: OnboardingState) -> Path:
    root = Path(project_root).resolve()
    target = root / "runs" / "m8"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "onboarding_contract.json"
    payload = {
        "state": asdict(state),
        "questions": [asdict(question) for question in questions_needed(state)],
        "capabilities": capabilities(state),
        "maximum_questions": 5,
        "unknown_policy": "An unknown answer disables dependent calculation; no default is invented.",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
