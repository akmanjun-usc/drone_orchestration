"""
System prompt for the agentic drone loop.

This is different from the GSCE code-generation prompt.
Instead of asking the LLM to write a complete program,
it asks the LLM to decide ONE next action given current state,
goal, and recent history.
"""

from skills.registry import build_skill_api_doc
from drone.config import SIM_CONFIG


_AGENT_SYSTEM_PROMPT_TEMPLATE = """\
You are an autonomous drone agent running inside a perceive-decide-act loop.

At each step you receive:
  - Your current goal
  - The drone's current sensor state
  - A log of recent steps (what you did and what happened)

Your job is to decide the single best next action to take.

## Output format

Respond with exactly ONE Python function call and nothing else.
No import statements. No explanations. No code blocks. Just one line.

Examples of valid responses:
  fly_to(client, x=10, y=5, altitude_m=8)
  hover(client, duration_s=2)
  capture_image(client, save_path="photo_001.png")
  takeoff(client, altitude_m=5)
  return_home(client)

If the goal is complete, respond with exactly:
  GOAL_COMPLETE

If you are stuck and cannot make progress, respond with:
  GOAL_ABORT: <one sentence reason>

## Rules

- Only call functions from the Skill APIs listed below.
- NEVER write import statements.
- NEVER instantiate any class.
- NEVER use dot-module notation like drone.something().
- The variable `client` is already defined. Never redefine it.
- Think about whether the drone is landed before issuing movement commands.
  If is_landed is True, call takeoff(client) first.
- Check constraints before choosing parameters:
  max altitude {max_alt}m, max speed {max_speed}m/s.
- Do not repeat the same action if it already failed.
- Make progress toward the goal every step. Hovering in place repeatedly
  is not progress. If stuck, try a different approach.

## Skill APIs

{skill_apis}
"""


def build_agent_system_prompt() -> str:
    """Build the complete agent system prompt with skill APIs injected."""
    return _AGENT_SYSTEM_PROMPT_TEMPLATE.format(
        max_alt=SIM_CONFIG.max_altitude_m,
        max_speed=SIM_CONFIG.max_speed_ms,
        skill_apis=build_skill_api_doc(),
    )


def build_agent_user_message(
    goal_description: str,
    completion_hint: str,
    step_num: int,
    max_steps: int,
    state_text: str,
    memory_text: str,
    fleet_text: str | None = None,
) -> str:
    """
    Build the user message for one agent step.

    This is what changes every iteration. The system prompt stays fixed.
    """
    parts = [
        f"## Goal",
        f"{goal_description}",
        f"Done when: {completion_hint}",
        f"",
        f"## Current step",
        f"Step {step_num} of {max_steps}",
        f"",
        f"## Drone state",
        state_text,
    ]

    if fleet_text:
        parts += ["", "## Fleet state", fleet_text]

    parts += [
        "",
        "## Recent history",
        memory_text,
        "",
        "What is the single best next action?",
    ]

    return "\n".join(parts)
