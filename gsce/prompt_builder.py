"""
GSCE prompt builder.

Assembles the four sections — Guidelines, Skill APIs,
Constraints, Examples — into a single system prompt string
ready to send to any LLM provider.
"""

from gsce.guidelines import GUIDELINES
from gsce.constraints import build_constraints_section
from gsce.examples import build_examples_section
from skills.registry import build_skill_api_doc


def build_system_prompt() -> str:
    """
    Assemble and return the complete GSCE system prompt.

    Section order follows the paper:
        G — Guidelines
        S — Skill APIs
        C — Constraints
        E — Examples
    """
    sections = [
        GUIDELINES.strip(),
        build_skill_api_doc().strip(),
        build_constraints_section().strip(),
        build_examples_section().strip(),
    ]
    return "\n\n---\n\n".join(sections)


if __name__ == "__main__":
    """
    Run directly to preview the assembled prompt and token estimate.
        python -m gsce.prompt_builder
    """
    prompt = build_system_prompt()
    char_count = len(prompt)
    # Rough token estimate: 1 token ~ 4 chars for English text
    token_estimate = char_count // 4

    print(prompt)
    print("\n" + "=" * 60)
    print(f"Characters : {char_count:,}")
    print(f"Token est. : ~{token_estimate:,}")
