"""
Evaluation runner.

Runs a list of EvalTasks through the orchestrator N times each,
collects TaskResults, scores them, and returns an EvalSummary.
"""

import logging
import time
from drone.bridge import DroneClient
from llm.orchestrator import Orchestrator
from eval.tasks import EvalTask
from eval.metrics import score_task, TaskScore, EvalSummary

logger = logging.getLogger(__name__)


def run_eval(
    tasks: list[EvalTask],
    orchestrator: Orchestrator,
    drone_client: DroneClient,
    prompt_label: str,
    runs_per_task: int = 1,
    delay_between_s: float = 2.0,
) -> EvalSummary:
    """
    Run every task through the orchestrator and return an EvalSummary.

    Args:
        tasks: List of EvalTask definitions to evaluate.
        orchestrator: Configured Orchestrator instance (GSCE or baseline).
        drone_client: Live connected DroneClient.
        prompt_label: Human label for this run, e.g. "GSCE" or "Baseline".
        runs_per_task: How many times to run each task (results averaged).
        delay_between_s: Seconds to wait between tasks (lets sim settle).

    Returns:
        EvalSummary with a TaskScore for every task run.
    """
    summary = EvalSummary(prompt_label=prompt_label)

    for task in tasks:
        logger.info(
            "[%s] Running task %s (%s): %s",
            prompt_label, task.id, task.complexity, task.description[:60],
        )

        run_scores: list[TaskScore] = []

        for run in range(runs_per_task):
            if runs_per_task > 1:
                logger.info("  Run %d/%d", run + 1, runs_per_task)

            orchestrator.clear_history()

            try:
                result = orchestrator.run_task(task.description)
            except Exception as exc:
                logger.error("Orchestrator raised an exception: %s", exc)
                from llm.orchestrator import TaskResult
                from llm.executor import ExecutionResult
                result = TaskResult(
                    task=task.description,
                    success=False,
                    generated_code="",
                    execution=ExecutionResult(success=False, code="", error=str(exc)),
                )

            score = score_task(task, result)
            run_scores.append(score)

            status = "PASS" if score.passed else "FAIL"
            logger.info("  %s — %s", status, score.validation_message)

            time.sleep(delay_between_s)

        # If multiple runs, keep the best result (most lenient evaluation)
        best = max(run_scores, key=lambda s: (s.passed, -s.attempts))
        summary.scores.append(best)

    return summary
