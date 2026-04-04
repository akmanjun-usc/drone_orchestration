"""
Orchestrator.

The main loop: takes a natural language task, calls the LLM,
extracts the generated code, executes it on the drone, and
logs the result. Supports multi-turn conversations so the
LLM can see previous attempts.
"""

import logging
from dataclasses import dataclass, field

from drone.bridge import DroneClient
from gsce.prompt_builder import build_system_prompt
from llm.provider import LLMProvider, CompletionRequest, Message
from llm.code_extractor import extract_code
from llm.executor import execute_code, ExecutionResult

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
        self.system_prompt = system_prompt or build_system_prompt()
        self._history: list[Message] = []

    def run_task(self, task: str, use_history: bool = False) -> TaskResult:
        """
        Run a single natural language task.

        Args:
            task: The task description in plain English.
            use_history: If True, include previous turns so the LLM can
                         learn from earlier attempts in this session.

        Returns:
            TaskResult with success flag, code, and token usage.
        """
        logger.info("Task: %s", task)

        messages = list(self._history) if use_history else []
        messages.append(Message(role="user", content=task))

        last_result: TaskResult | None = None

        for attempt in range(1, self.max_retries + 2):
            logger.info("Attempt %d/%d", attempt, self.max_retries + 1)

            request = CompletionRequest(
                system_prompt=self.system_prompt,
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
