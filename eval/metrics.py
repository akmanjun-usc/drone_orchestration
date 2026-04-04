"""
Evaluation metrics.

Computes per-task and aggregate scores matching
the metrics used in the GSCE paper.
"""

from dataclasses import dataclass, field
from eval.tasks import EvalTask
from llm.orchestrator import TaskResult


@dataclass
class TaskScore:
    task_id: str
    complexity: str
    passed: bool
    validation_message: str
    constraint_violations: list[str]
    attempts: int
    input_tokens: int
    output_tokens: int
    model: str


@dataclass
class EvalSummary:
    prompt_label: str          # e.g. "GSCE" or "Baseline"
    scores: list[TaskScore] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.scores)

    @property
    def passed(self) -> int:
        return sum(1 for s in self.scores if s.passed)

    @property
    def success_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def by_complexity(self, level: str) -> "EvalSummary":
        sub = EvalSummary(prompt_label=self.prompt_label)
        sub.scores = [s for s in self.scores if s.complexity == level]
        return sub

    @property
    def constraint_violation_rate(self) -> float:
        tasks_with_violations = sum(1 for s in self.scores if s.constraint_violations)
        return tasks_with_violations / self.total if self.total else 0.0


def score_task(task: EvalTask, result: TaskResult) -> TaskScore:
    """
    Score a single task result against its validator and constraint list.
    """
    passed, message = task.validate(result)

    # Check expected constraint keywords appear in generated code
    violations = []
    for kw in task.expected_constraints:
        if kw.lower() not in result.generated_code.lower():
            violations.append(f"Missing constraint keyword: '{kw}'")

    # A task fails if any expected constraint is missing
    if violations:
        passed = False
        message += f" | Constraint violations: {violations}"

    return TaskScore(
        task_id=task.id,
        complexity=task.complexity,
        passed=passed,
        validation_message=message,
        constraint_violations=violations,
        attempts=result.attempts,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        model=result.model,
    )
