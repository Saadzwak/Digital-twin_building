"""At-most-five human questions for facts no supplied plan can establish."""

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


@dataclass(frozen=True)
class OnboardingQuestion:
    key: str
    prompt: str
    why_needed: str
    enables: tuple[str, ...]


QUESTION_BANK: tuple[OnboardingQuestion, ...] = (
    OnboardingQuestion(
        "thermal_boundary",
        "Which polygon and which floors match the metered thermal perimeter?",
        "The plans alone do not link their geometry to the metered indoor-temperature zone.",
        ("thermal_boundary",),
    ),
    OnboardingQuestion(
        "north_azimuth",
        "What is the north azimuth on the plan?",
        "Orientation cannot be reliably inferred from the supplied PDFs.",
        ("facade_orientation",),
    ),
    OnboardingQuestion(
        "floor_heights",
        "Which finished floor-to-floor heights should be used per level of the thermal perimeter?",
        "Volume and facade areas require confirmed heights.",
        ("volume", "facade_area"),
    ),
    OnboardingQuestion(
        "glazing_geometry",
        "Do you confirm the drawn glazing and its height, or declare them unknown?",
        "The glazing ratio cannot be inferred from unvalidated PDF outlines.",
        ("glazing_ratio",),
    ),
)


def questions_needed(state: OnboardingState) -> tuple[OnboardingQuestion, ...]:
    """Ask only unresolved non-extractable facts, in a stable priority order."""

    questions = tuple(question for question in QUESTION_BANK if getattr(state, question.key) == "not_asked")
    if len(questions) > 5:
        raise AssertionError("Onboarding must never exceed five questions.")
    return questions


def capabilities(state: OnboardingState) -> dict[str, bool]:
    """Unknown answers disable dependent computation; r'' remains an M7 free fit."""

    boundary = state.thermal_boundary == "known"
    north = state.north_azimuth == "known"
    heights = state.floor_heights == "known"
    glazing = state.glazing_geometry == "known"
    return {
        "thermal_boundary": boundary,
        "facade_orientation": boundary and north,
        "facade_area": boundary and north and heights,
        "volume": boundary and heights,
        "glazing_ratio": boundary and north and heights and glazing,
        # Geometry makes one shared r'' identifiable in a candidate; it does
        # not ask the user to freeze r'' as a documented constant.
        "geometry_constrained_candidate": boundary and north and heights,
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
        "parameter_policy": "M7 retains one shared r'' free parameter; no user-supplied resistance is requested.",
        "unknown_policy": "An unknown answer disables dependent calculation; no default is invented.",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
