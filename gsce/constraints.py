"""
GSCE — C: Constraints

Safety and operational rules the LLM must apply when generating
control code. These are injected as natural language rules so the
LLM reasons about them, not just checks them numerically.
"""

from drone.config import SIM_CONFIG

# You can add, remove, or edit constraints freely.
# Each entry is one natural-language rule.
_CONSTRAINTS: list[str] = [
    f"Never fly above {SIM_CONFIG.max_altitude_m} metres AGL. "
    f"If a task requests a higher altitude, clamp to {SIM_CONFIG.max_altitude_m} m.",

    f"Never exceed {SIM_CONFIG.max_speed_ms} m/s. "
    f"If a task requests a higher speed, clamp to {SIM_CONFIG.max_speed_ms} m/s.",

    f"If battery level drops below {SIM_CONFIG.min_battery_pct}%, "
    f"call return_home(client) immediately before doing anything else.",

    "Always call takeoff() before any movement command if the drone is landed. "
    "Check get_state(client)['is_landed'] if uncertain.",

    "End every mission by calling return_home(client) unless the task "
    "explicitly says to stay in position.",

    "Never fly a negative altitude (underground). Minimum altitude for any "
    "movement command is 1.0 m AGL.",

    "When performing a survey or search, complete the full pattern before "
    "returning. Do not abort mid-pattern unless a safety constraint is triggered.",

    "If any skill function raises an exception, do not retry silently. "
    "Let the exception propagate so the orchestrator can log it.",

    f"The simulation supports a maximum of {SIM_CONFIG.max_drones} drones. "
    f"Before spawning a new drone, check list_drones(client) to see how many "
    f"are already active. Never call spawn_drone() if {SIM_CONFIG.max_drones} "
    f"drones are already active.",

    "After spawning a new drone, always call select_drone(client, name) "
    "followed by takeoff(client) before issuing movement commands to it.",
]


def build_constraints_section() -> str:
    """
    Format all constraints as a numbered list for the system prompt.
    """
    lines = ["## Constraints\n"]
    lines += [f"{i + 1}. {c}" for i, c in enumerate(_CONSTRAINTS)]
    return "\n".join(lines)


def get_constraints() -> list[str]:
    """Return the raw constraint strings (used by evaluator in Phase 5)."""
    return list(_CONSTRAINTS)
