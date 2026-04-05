"""
Orchestrator.

The main loop: takes a natural language task, calls the LLM,
extracts the generated code, executes it on the drone, and
logs the result. Supports multi-turn conversations so the
LLM can see previous attempts.

Fleet planning:
  Before generating code, a lightweight planning LLM call
  analyzes the task to decide how many drones are needed.
  The orchestrator spawns them automatically, then injects
  a "Fleet Decision" section into the code-generation prompt
  so the LLM knows exactly which drones are available.
"""

import logging
from dataclasses import dataclass, field

from drone.bridge import DroneClient
from gsce.prompt_builder import build_system_prompt
from llm.provider import LLMProvider, CompletionRequest, Message
from llm.code_extractor import extract_code
from llm.executor import execute_code, ExecutionResult
from llm.fleet_planner import FleetPlan, plan_fleet, build_fleet_context

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    task: str
    success: bool
    generated_code: str
    execution: ExecutionResult
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    attempts: int = 1
    fleet_plan: FleetPlan | None = None


class Orchestrator:
    """
    GSCE drone orchestrator.

    Usage:
        orch = Orchestrator(provider, model, client)
        result = orch.run_task("Survey a 30x30 area at 15m altitude")
    """

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        drone_client: DroneClient,
        max_retries: int = 2,
        system_prompt: str | None = None,
    ):
        self.provider = provider
        self.model = model
        self.drone_client = drone_client
        self.max_retries = max_retries
        self._base_system_prompt = system_prompt or build_system_prompt()
        self._history: list[Message] = []

    def run_task(self, task: str, use_history: bool = False) -> TaskResult:
        """
        Run a single natural language task.

        Steps:
          1. Fleet planning — ask the LLM how many drones this task needs,
             then spawn them automatically.
          2. Code generation — call the LLM with the task + fleet context
             to generate executable Python code.
          3. Execution — run the generated code against the live drone(s).
          4. Self-correction — if execution fails, feed the error back
             to the LLM and retry (up to max_retries times).

        Args:
            task: The task description in plain English.
            use_history: If True, include previous turns so the LLM can
                         learn from earlier attempts in this session.

        Returns:
            TaskResult with success flag, code, fleet plan, and token usage.
        """
        logger.info("Task: %s", task)

        # --- Step 1: Fleet planning --------------------------------------
        fleet = plan_fleet(
            provider=self.provider,
            model=self.model,
            task=task,
            client=self.drone_client,
        )
        logger.info(
            "Fleet decision: %d drone(s) — %s",
            fleet.drone_count,
            fleet.reasoning,
        )

        # Build the augmented system prompt with fleet context
        fleet_section = build_fleet_context(fleet)
        system_prompt = (
            self._base_system_prompt
            + "\n\n---\n\n"
            + fleet_section
        )

        # --- Step 2+3+4: Code generation loop -----------------------------
        messages = list(self._history) if use_history else []
        messages.append(Message(role="user", content=task))

        last_result: TaskResult | None = None

        for attempt in range(1, self.max_retries + 2):
            logger.info("Attempt %d/%d", attempt, self.max_retries + 1)

            request = CompletionRequest(
                system_prompt=system_prompt,
                messages=messages,
                model=self.model,
            )

            response = self.provider.complete(request)
            logger.info(
                "LLM response (%s): %d input + %d output tokens",
                response.model,
                response.input_tokens,
                response.output_tokens,
            )

            try:
                code = extract_code(response.content)
            except ValueError as exc:
                logger.error("Code extraction failed: %s", exc)
                last_result = TaskResult(
                    task=task,
                    success=False,
                    generated_code="",
                    execution=ExecutionResult(
                        success=False, code="", error=str(exc)
                    ),
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    model=response.model,
                    attempts=attempt,
                    fleet_plan=fleet,
                )
                break

            exec_result = execute_code(self.drone_client, code)

            last_result = TaskResult(
                task=task,
                success=exec_result.success,
                generated_code=code,
                execution=exec_result,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                model=response.model,
                attempts=attempt,
                fleet_plan=fleet,
            )

            if exec_result.success:
                # Store the successful exchange in history
                messages.append(Message(role="assistant", content=response.content))
                self._history = messages if use_history else self._history
                break

            if attempt <= self.max_retries:
                # Feed the error back to the LLM for self-correction
                error_msg = (
                    f"Your code raised an exception:\n"
                    f"{exec_result.error}\n\n"
                    f"Traceback:\n{exec_result.traceback}\n\n"
                    f"Please fix the code and try again."
                )
                messages.append(Message(role="assistant", content=response.content))
                messages.append(Message(role="user", content=error_msg))
                logger.info("Retrying with error feedback...")

        return last_result

    def clear_history(self) -> None:
        """Reset the conversation history."""
        self._history = []
