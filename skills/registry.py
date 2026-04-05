"""
Skill registry.

Inspects every skill function and extracts its docstring.
The result is injected as the "S" (Skill APIs) section of
the GSCE system prompt in Phase 3.
"""

import inspect
import textwrap
from types import ModuleType

from skills import navigation, perception, mission, fleet

# Ordered list of skill modules — order determines prompt order
SKILL_MODULES: list[tuple[str, ModuleType]] = [
    ("Fleet Management", fleet),
    ("Navigation", navigation),
    ("Perception", perception),
    ("Mission", mission),
]

# Functions to exclude (internal helpers, not for LLM)
_EXCLUDE = {"__builtins__"}


def get_skill_functions() -> dict[str, callable]:
    """
    Return a flat name->callable dict of every public skill function.
    Used by the executor to build the safe exec namespace.
    """
    funcs: dict[str, callable] = {}
    for _, module in SKILL_MODULES:
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("_") and name not in _EXCLUDE:
                funcs[name] = obj
    return funcs


def build_skill_api_doc() -> str:
    """
    Build a human-readable (and LLM-readable) API reference string.

    Each function's signature and docstring is included verbatim.
    This string becomes the "S" block in the GSCE system prompt.
    """
    sections: list[str] = []

    for section_name, module in SKILL_MODULES:
        lines = [f"## {section_name} skills\n"]
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("_") or name in _EXCLUDE:
                continue
            sig = inspect.signature(obj)
            doc = inspect.getdoc(obj) or "(no docstring)"
            lines.append(f"### {name}{sig}")
            lines.append(textwrap.indent(doc, "    "))
            lines.append("")
        sections.append("\n".join(lines))

    return "\n".join(sections)


if __name__ == "__main__":
    print(build_skill_api_doc())
