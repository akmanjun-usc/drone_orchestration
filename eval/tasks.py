"""
Evaluation task definitions.

Three complexity levels matching the GSCE paper's taxonomy.
Each task has a description and a validator function that
checks the execution result for success criteria.
"""

from dataclasses import dataclass, field
from typing import Callable
from llm.orchestrator import TaskResult


@dataclass
class EvalTask:
    id: str
    description: str
    complexity: str           # "simple" | "medium" | "complex"
    validate: Callable[[TaskResult], tuple[bool, str]]
    # Constraint keywords the generated code must respect
    expected_constraints: list[str] = field(default_factory=list)


def _code_contains(result: TaskResult, *keywords: str) -> bool:
    code = result.generated_code.lower()
    return all(kw.lower() in code for kw in keywords)


# ------------------------------------------------------------------
# Simple tasks — single-step, no constraint reasoning required
# ------------------------------------------------------------------

SIMPLE_TASKS: list[EvalTask] = [
    EvalTask(
        id="s1",
        description="Take off and hover at 5 metres altitude.",
        complexity="simple",
        validate=lambda r: (
            r.success and _code_contains(r, "takeoff"),
            "Expected takeoff call",
        ),
    ),
    EvalTask(
        id="s2",
        description="Fly to position x=15, y=10 at 8 metres altitude.",
        complexity="simple",
        validate=lambda r: (
            r.success and _code_contains(r, "fly_to"),
            "Expected fly_to call",
        ),
    ),
    EvalTask(
        id="s3",
        description="Capture a photo from the front camera.",
        complexity="simple",
        validate=lambda r: (
            r.success and _code_contains(r, "capture_image"),
            "Expected capture_image call",
        ),
    ),
]

# ------------------------------------------------------------------
# Medium tasks — multi-step, requires sequencing and constraint check
# ------------------------------------------------------------------

MEDIUM_TASKS: list[EvalTask] = [
    EvalTask(
        id="m1",
        description=(
            "Fly to x=20, y=0 at 10 metres. Hover for 3 seconds. "
            "Then fly to x=20, y=20. Return home."
        ),
        complexity="medium",
        validate=lambda r: (
            r.success
            and _code_contains(r, "fly_to")
            and _code_contains(r, "hover")
            and _code_contains(r, "return_home"),
            "Expected fly_to + hover + return_home",
        ),
    ),
    EvalTask(
        id="m2",
        description=(
            "Fly to 80 metres altitude and take a photo. "
            "(Note: maximum altitude is 50 metres.)"
        ),
        complexity="medium",
        expected_constraints=["altitude", "clamp", "50"],
        validate=lambda r: (
            r.success
            and "50" in r.generated_code
            and _code_contains(r, "capture_image"),
            "Expected altitude clamped to 50 m with photo",
        ),
    ),
    EvalTask(
        id="m3",
        description="Orbit the point x=0, y=0 at a radius of 20 metres and 12 metres altitude.",
        complexity="medium",
        validate=lambda r: (
            r.success and _code_contains(r, "orbit_point"),
            "Expected orbit_point call",
        ),
    ),
]

# ------------------------------------------------------------------
# Complex tasks — multi-objective, requires planning + constraint reasoning
# ------------------------------------------------------------------

COMPLEX_TASKS: list[EvalTask] = [
    EvalTask(
        id="c1",
        description=(
            "Survey a 60 x 60 metre area starting at x=0, y=0. "
            "Use 15 metres altitude and 10 metre row spacing. "
            "Save photos to 'eval_survey'. Then return home."
        ),
        complexity="complex",
        validate=lambda r: (
            r.success
            and _code_contains(r, "survey_grid")
            and _code_contains(r, "return_home"),
            "Expected survey_grid + return_home",
        ),
    ),
    EvalTask(
        id="c2",
        description=(
            "Find all objects matching 'Target_*'. "
            "For each one, fly to it and inspect from 4 angles at 8 metres altitude. "
            "Save photos named by target. Return home when done."
        ),
        complexity="complex",
        validate=lambda r: (
            r.success
            and _code_contains(r, "detect_object")
            and _code_contains(r, "inspect_point"),
            "Expected detect_object + inspect_point loop",
        ),
    ),
    EvalTask(
        id="c3",
        description=(
            "Search a circular area centred at x=0, y=0 with radius 40 metres "
            "at 20 metres altitude. Then fly to x=50, y=50 at 200 metres altitude "
            "and photograph the area. Return home. "
            "(Remember: maximum altitude is 50 metres.)"
        ),
        complexity="complex",
        expected_constraints=["altitude", "clamp", "50"],
        validate=lambda r: (
            r.success
            and _code_contains(r, "search_area")
            and "50" in r.generated_code
            and _code_contains(r, "capture_image"),
            "Expected search_area, altitude clamped to 50 m, capture_image",
        ),
    ),
]

ALL_TASKS = SIMPLE_TASKS + MEDIUM_TASKS + COMPLEX_TASKS
