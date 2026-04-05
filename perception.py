"""
Perception layer.

Reads the current drone state and formats it into a structured
text description the LLM can reason about at each agent step.
"""

from drone.bridge import DroneClient
from drone import primitives as prim


def observe(client: DroneClient) -> tuple[dict, str]:
    """
    Read the drone's current state and format it for the LLM.

    Returns:
        (state_dict, formatted_text) where state_dict is the raw
        dict from get_state() and formatted_text is a human-readable
        summary to include in the LLM prompt.
    """
    state = prim.get_state(client)

    lines = [
        f"Position  : x={state['x']:.1f}m  y={state['y']:.1f}m  alt={state['z_agl']:.1f}m AGL",
        f"Velocity  : vx={state['vx']:.1f}  vy={state['vy']:.1f}  vz={state['vz']:.1f} m/s",
        f"Heading   : yaw={state['yaw']:.1f} deg",
        f"Landed    : {state['is_landed']}",
        f"Drone     : {client.active_drone_name}",
    ]

    return state, "\n".join(lines)


def observe_fleet(client: DroneClient) -> str:
    """
    Read state for all active drones and format as a fleet summary.

    Used when the agent is managing multiple drones.
    """
    original = client.active_drone_name
    lines = []

    for name in client.get_active_drone_names():
        client.set_active_drone(name)
        state = prim.get_state(client)
        lines.append(
            f"  {name}: x={state['x']:.1f} y={state['y']:.1f} "
            f"alt={state['z_agl']:.1f}m  landed={state['is_landed']}"
        )

    client.set_active_drone(original)
    return "\n".join(lines) if lines else "  (no active drones)"
