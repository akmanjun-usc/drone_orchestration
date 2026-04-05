"""
Executor.

Runs LLM-generated code in a controlled namespace that
contains only the skill functions and the drone client.
Any exception raised by the code propagates up to the
orchestrator for logging.
"""

import logging
import traceback
from dataclasses import dataclass, field

from drone.bridge import DroneClient
from skills.registry import get_skill_functions

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    success: bool
    code: str
    stdout_lines: list[str] = field(default_factory=list)
    error: str | None = None
    traceback: str | None = None


def execute_code(client: DroneClient, code: str) -> ExecutionResult:
    """
    Execute generated Python code in a sandboxed namespace.

    The namespace contains:
        - client         : the live DroneClient
        - drone          : alias of client for compatibility
        - all skill functions from skills.registry

    Args:
        client: Connected DroneClient passed to every skill call.
        code:   Python source string extracted from the LLM response.

    Returns:
        ExecutionResult with success flag, captured prints, and any error.
    """
    captured: list[str] = []

    def _print(*args, **kwargs):
        line = " ".join(str(a) for a in args)
        captured.append(line)
        logger.info("[drone] %s", line)

    namespace: dict = {
        "client": client,
        # Some models still emit `drone` as the connected client variable.
        # Keep this as a compatibility alias while the prompt steers them to `client`.
        "drone": client,
        "print": _print,
        "__builtins__": {"len": len, "range": range, "int": int, "float": float,
                         "str": str, "list": list, "dict": dict, "bool": bool,
                         "True": True, "False": False, "None": None,
                         "enumerate": enumerate, "zip": zip, "max": max, "min": min,
                         "abs": abs, "round": round, "isinstance": isinstance,
                         "Exception": Exception, "ValueError": ValueError,
                         "RuntimeError": RuntimeError},
    }
    namespace.update(get_skill_functions())

    logger.info("Executing generated code (%d lines):\n%s", code.count("\n") + 1, code)

    try:
        exec(compile(code, "<llm_generated>", "exec"), namespace)
        return ExecutionResult(success=True, code=code, stdout_lines=captured)
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("Execution failed: %s\n%s", exc, tb)
        return ExecutionResult(
            success=False,
            code=code,
            stdout_lines=captured,
            error=str(exc),
            traceback=tb,
        )
