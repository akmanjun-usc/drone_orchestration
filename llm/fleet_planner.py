"""
Fleet planner.

Before the code-generation LLM call, a lightweight planning call
asks the LLM to analyze the task and decide how many drones are
needed (1–10). The Orchestrator then automatically spawns that
many drones and injects a "Fleet Decision" section into the
system prompt so the code-generation call knows which drones
are available.

This keeps the user's natural-language task unchanged — the agent
autonomously decides the fleet size.
"""

import json
import logging
import re
from dataclasses import dataclass

from drone.bridge import DroneClient
from drone.config import SIM_CONFIG
from llm.provider import LLMProvider, CompletionRequest, Message

logger = logging.getLogger(__name__)


# System prompt for the fleet-planning call (kept small & focused).
_FLEET_PLANNER_PROMPT = f"""\
You are a fleet planning assistant for a drone simulation.

Given a task description, decide how many drones (1–{SIM_CONFIG.max_drones}) are \
needed to accomplish it efficiently. Consider:

- Simple tasks (single fly-to, single inspection, hover) → 1 drone
- Tasks mentioning "multiple drones", "swarm", "fleet", or "simultaneously" → \
use the number mentioned, or 2–4 if unspecified
- Area surveys or search-and-rescue → 2–4 drones for parallel coverage
- Tasks explicitly requesting N drones → use N (capped at {SIM_CONFIG.max_drones})
- Perimeter patrol or multi-point inspection → 2–3 drones

Respond with ONLY a JSON object on a single line, nothing else:
{{"drone_count": <int>, "reasoning": "<one sentence>"}}
"""


@dataclass
class FleetPlan:
    """Result of the fleet planning step."""
    drone_count: int
    reasoning: str
    active_drone_names: list[str]


def plan_fleet(
    provider: LLMProvider,
    model: str,
    task: str,
    client: DroneClient,
) -> FleetPlan:
    """
    Ask the LLM how many drones this task needs, then spawn them.

    Args:
        provider: The LLM provider to use for the planning call.
        model: Model string.
        task: The user's natural-language task description.
        client: Connected DroneClient with the drone pool.

    Returns:
        FleetPlan with the decided count, reasoning, and spawned names.
    """
    # --- Phase 1: Ask the LLM for a fleet size decision -----------------
    request = CompletionRequest(
        system_prompt=_FLEET_PLANNER_PROMPT,
        messages=[Message(role="user", content=task)],
        model=model,
        max_tokens=256,
        temperature=0.0,
    )

    response = provider.complete(request)
    logger.info(
        "Fleet planner response (%d tokens): %s",
        response.output_tokens,
        response.content.strip(),
    )

    # --- Phase 2: Parse the JSON response --------------------------------
    drone_count = 1
    reasoning = "default: single drone"

    try:
        # Extract JSON from the response (tolerant of markdown wrapping)
        text = response.content.strip()
        # Strip markdown code fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        parsed = json.loads(text)
        drone_count = int(parsed.get("drone_count", 1))
        reasoning = str(parsed.get("reasoning", ""))
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning(
            "Could not parse fleet planner response, defaulting to 1 drone: %s",
            exc,
        )

    # Clamp to valid range
    drone_count = max(1, min(drone_count, SIM_CONFIG.max_drones))

    # --- Phase 3: Spawn drones as needed ---------------------------------
    current_active = client.get_active_drone_names()
    drones_to_spawn = drone_count - len(current_active)

    for _ in range(drones_to_spawn):
        try:
            client.spawn_drone()
        except RuntimeError as exc:
            logger.warning("Could not spawn additional drone: %s", exc)
            break

    active_names = client.get_active_drone_names()
    logger.info(
        "Fleet plan: %d drone(s) requested, %d active → %s  |  %s",
        drone_count,
        len(active_names),
        active_names,
        reasoning,
    )

    return FleetPlan(
        drone_count=drone_count,
        reasoning=reasoning,
        active_drone_names=active_names,
    )


def build_fleet_context(plan: FleetPlan) -> str:
    """
    Build a prompt section that tells the code-generation LLM
    which drones are available and what the plan decided.

    This is injected into the system prompt before the code call.
    """
    names = ", ".join(plan.active_drone_names)
    lines = [
        "## Fleet Decision (auto-planned)",
        "",
        f"This task requires **{plan.drone_count}** drone(s).",
        f"Reasoning: {plan.reasoning}",
        f"Active drones: {names}",
        "",
    ]

    if plan.drone_count == 1:
        lines.append(
            "Use only Drone1 (already selected). "
            "Do NOT call spawn_drone() or select_drone()."
        )
    else:
        lines.append(
            f"All {plan.drone_count} drones are already spawned and armed. "
            f"Do NOT call spawn_drone(). "
            f"Use select_drone(client, name) to switch between them. "
            f"Drone1 is currently selected."
        )
        lines.append("")
        lines.append(
            "For each drone: select it, takeoff, execute its portion of "
            "the task, then move to the next drone."
        )

    return "\n".join(lines)
