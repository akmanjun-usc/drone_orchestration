"""
Executor.

Runs LLM-generated code in a sandboxed namespace containing only
the skill functions and the live drone client.

Also validates code before running it to catch common LLM hallucination
patterns early and return a clear error message instead of a confusing
AttributeError.
"""

import re
import logging
import traceback
from dataclasses import dataclass, field

from drone.bridge import DroneClient
from skills.registry import get_skill_functions

logger = logging.getLogger(__name__)

# Patterns that indicate the LLM hallucinated instead of following instructions.
# Each is a (regex_pattern, human_readable_description) tuple.
_HALLUCINATION_PATTERNS = [
    (r"^\s*import\s+\w+",           "import statement (no imports are allowed)"),
    (r"^\s*from\s+\w+\s+import",    "from-import statement (no imports are allowed)"),
    (r"\bDroneClient\s*\(",         "DroneClient() constructor (client is already defined)"),
    (r"\bDrone\s*\(",               "Drone() constructor (client is already defined)"),
    (r"\bWorld\s*\(",               "World() constructor (not available in this namespace)"),
    (r"\bProjectAirSimClient\s*\(", "ProjectAirSimClient() constructor (not available)"),
    (r"\bairsim\.",                 "airsim module access (no modules are available)"),
    (r"\bdrone\.\w+\s*\(",          "drone.method() call (use skill functions directly, not module notation)"),
    (r"\bclient\s*=\s*\w+\s*\(",   "client reassignment (client is already defined, do not redefine it)"),
]


@dataclass
class ExecutionResult:
    success: bool
    code: str
    stdout_lines: list[str] = field(default_factory=list)
    error: str | None = None
    traceback: str | None = None


def _validate_code(code: str) -> str | None:
    """
    Scan generated code for hallucination patterns before running it.

    Returns a human-readable error string if a problem is found,
    or None if the code looks safe to run.
    """
    for line in code.splitlines():
        for pattern, description in _HALLUCINATION_PATTERNS:
            if re.search(pattern, line):
                return (
                    f"Generated code contains a forbidden pattern: {description}.\n"
                    f"Offending line: {line.strip()}\n"
                    f"Only use the skill functions listed in the system prompt. "
                    f"The variable `client` is already defined — do not create or import anything."
                )
    return None


def execute_code(client: DroneClient, code: str) -> ExecutionResult:
    """
    Validate then execute generated Python code in a sandboxed namespace.

    The namespace contains:
        client              the live connected DroneClient
        all skill functions from skills.registry

    Args:
        client: Connected DroneClient passed to every skill call.
        code:   Python source string extracted from the LLM response.

    Returns:
        ExecutionResult with success flag, captured prints, and any error.
    """
    # Validate before executing
    validation_error = _validate_code(code)
    if validation_error:
        logger.error("Code validation failed: %s", validation_error)
        return ExecutionResult(
            success=False,
            code=code,
            error=validation_error,
        )

    captured: list[str] = []

    def _print(*args, **kwargs):
        line = " ".join(str(a) for a in args)
        captured.append(line)
        logger.info("[drone] %s", line)

    namespace: dict = {
        "client": client,
        "print": _print,
        "__builtins__": {
            "len": len, "range": range, "int": int, "float": float,
            "str": str, "list": list, "dict": dict, "bool": bool,
            "True": True, "False": False, "None": None,
            "enumerate": enumerate, "zip": zip, "max": max, "min": min,
            "abs": abs, "round": round, "isinstance": isinstance,
            "Exception": Exception, "ValueError": ValueError,
            "RuntimeError": RuntimeError,
        },
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
