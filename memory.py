"""
Agent memory.

Records what the drone observed and did at each step.
The agent feeds the last N steps into every LLM prompt
so it can reason about what worked and avoid repeating mistakes.
"""

from dataclasses import dataclass, field


@dataclass
class Step:
    """One perceive-decide-act cycle."""
    step_num: int
    state_summary: str      # Formatted observation at this step
    action_taken: str       # The action the LLM chose (one function call)
    outcome: str            # "success", "error: <msg>", or "skipped"
    drone_name: str = "Drone1"


class AgentMemory:
    """
    Short-term memory for one drone agent session.

    Keeps the full step log but only surfaces the last
    `context_window` steps to the LLM prompt to stay
    within token limits.
    """

    def __init__(self, context_window: int = 5):
        self.context_window = context_window
        self._steps: list[Step] = []

    def record(
        self,
        step_num: int,
        state_summary: str,
        action_taken: str,
        outcome: str,
        drone_name: str = "Drone1",
    ) -> None:
        """Append a completed step to memory."""
        self._steps.append(Step(
            step_num=step_num,
            state_summary=state_summary,
            action_taken=action_taken,
            outcome=outcome,
            drone_name=drone_name,
        ))

    def recent(self) -> list[Step]:
        """Return the most recent context_window steps."""
        return self._steps[-self.context_window:]

    def format_for_prompt(self) -> str:
        """
        Format recent steps as a readable block for the LLM prompt.

        Returns an empty string if no steps have been recorded yet.
        """
        steps = self.recent()
        if not steps:
            return "(No previous steps — this is the first action.)"

        lines = []
        for s in steps:
            lines.append(f"Step {s.step_num} [{s.drone_name}]:")
            lines.append(f"  Observed : {s.state_summary}")
            lines.append(f"  Action   : {s.action_taken}")
            lines.append(f"  Outcome  : {s.outcome}")
        return "\n".join(lines)

    def all_actions(self) -> list[str]:
        """Return every action taken so far, for deduplication checks."""
        return [s.action_taken for s in self._steps]

    def last_outcome(self) -> str | None:
        """Return the outcome of the most recent step, or None."""
        return self._steps[-1].outcome if self._steps else None

    def clear(self) -> None:
        self._steps.clear()
