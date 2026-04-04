"""
GSCE vs baseline comparison.

Builds two orchestrators — one with the full GSCE prompt (G+S+C+E)
and one with the baseline prompt (G+S only, no constraints or examples)
— runs the same task list through both, and returns the pair of
EvalSummary objects for report.py to format.
"""

import logging
from drone.bridge import DroneClient
from llm.provider import LLMProvider
from llm.orchestrator import Orchestrator
from gsce.prompt_builder import build_system_prompt
from gsce.guidelines import GUIDELINES
from skills.registry import build_skill_api_doc
from eval.tasks import EvalTask
from eval.metrics import EvalSummary
from eval.runner import run_eval

logger = logging.getLogger(__name__)


def build_baseline_prompt() -> str:
    """
    Baseline prompt: Guidelines + Skill APIs only.
    No constraints section, no examples — mirrors prior work
    referenced in the GSCE paper.
    """
    return (
        GUIDELINES.strip()
        + "\n\n---\n\n"
        + build_skill_api_doc().strip()
    )


def compare(
    tasks: list[EvalTask],
    provider: LLMProvider,
    model: str,
    drone_client: DroneClient,
    runs_per_task: int = 1,
) -> tuple[EvalSummary, EvalSummary]:
    """
    Run all tasks under GSCE and baseline prompts and return both summaries.

    Args:
        tasks: Task list to evaluate (use ALL_TASKS or a subset).
        provider: LLM provider instance.
        model: Model string to use.
        drone_client: Live connected DroneClient.
        runs_per_task: Repetitions per task for statistical stability.

    Returns:
        (gsce_summary, baseline_summary)
    """
    logger.info("=== Starting GSCE vs Baseline comparison ===")
    logger.info("Tasks: %d  |  Runs per task: %d  |  Model: %s", len(tasks), runs_per_task, model)

    # GSCE: full G+S+C+E prompt
    gsce_orch = Orchestrator(
        provider=provider,
        model=model,
        drone_client=drone_client,
        system_prompt=build_system_prompt(),
    )
    logger.info("--- Running GSCE prompt ---")
    gsce_summary = run_eval(
        tasks, gsce_orch, drone_client,
        prompt_label="GSCE",
        runs_per_task=runs_per_task,
    )

    # Baseline: G+S only
    baseline_orch = Orchestrator(
        provider=provider,
        model=model,
        drone_client=drone_client,
        system_prompt=build_baseline_prompt(),
    )
    logger.info("--- Running Baseline prompt ---")
    baseline_summary = run_eval(
        tasks, baseline_orch, drone_client,
        prompt_label="Baseline",
        runs_per_task=runs_per_task,
    )

    return gsce_summary, baseline_summary
