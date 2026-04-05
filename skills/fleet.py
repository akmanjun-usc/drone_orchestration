"""
Fleet management skills.

These functions let the LLM (and the REPL user) activate new drones
from the pre-defined pool and switch control between them.

Project AirSim does not support runtime vehicle spawning, so all
drones are declared in the scene config JSONC upfront.  "Spawning"
here means activating an idle drone so it can receive API commands.
"""

import logging

from drone.bridge import DroneClient

logger = logging.getLogger(__name__)


def spawn_drone(client: DroneClient, name: str | None = None) -> str:
    """
    Activate a new drone from the pre-defined pool.

    The scene supports up to 10 drones (Drone1 – Drone10).
    If no name is given, the next available drone is chosen
    automatically (e.g. Drone2, Drone3, …).

    Args:
        client: Connected DroneClient.
        name: Optional explicit drone name (e.g. "Drone3").
              If omitted, the lowest-numbered inactive drone is used.

    Returns:
        The name of the newly activated drone (e.g. "Drone3").

    Raises:
        RuntimeError: If all 10 drones are already active or the
                      requested name is invalid / already active.

    Example:
        new_name = spawn_drone(client)
        print(f"Spawned {new_name}")
    """
    activated = client.spawn_drone(name)
    logger.info("spawn_drone → %s", activated)
    return activated


def list_drones(client: DroneClient) -> list[str]:
    """
    Return the names of all currently active (spawned) drones.

    Args:
        client: Connected DroneClient.

    Returns:
        List of drone name strings, e.g. ["Drone1", "Drone2"].

    Example:
        names = list_drones(client)
        print(f"{len(names)} drones active")
    """
    names = client.get_active_drone_names()
    logger.info("list_drones → %s", names)
    return names


def select_drone(client: DroneClient, name: str) -> None:
    """
    Switch subsequent commands to target a different active drone.

    After calling this, every navigation or perception command
    (fly_to, hover, get_state, capture_image, …) will operate on
    the selected drone until select_drone is called again.

    Args:
        client: Connected DroneClient.
        name: Name of an already-active drone (e.g. "Drone2").

    Raises:
        ValueError: If the drone is not active.

    Example:
        select_drone(client, "Drone2")
        fly_to(client, x=10, y=0, altitude_m=8)   # moves Drone2
    """
    client.set_active_drone(name)
    logger.info("select_drone → %s", name)


def get_active_drone(client: DroneClient) -> str:
    """
    Return the name of the drone that commands currently target.

    Args:
        client: Connected DroneClient.

    Returns:
        The name of the currently selected drone, e.g. "Drone1".

    Example:
        current = get_active_drone(client)
        print(f"Currently controlling {current}")
    """
    name = client.active_drone_name
    logger.info("get_active_drone → %s", name)
    return name


def get_fleet_status(client: DroneClient) -> dict:
    """
    Return position and status of every active drone.

    Args:
        client: Connected DroneClient.

    Returns:
        Dict mapping drone names to their state dicts.
        Each state dict has keys: x, y, z_agl, vx, vy, vz,
        roll, pitch, yaw, is_landed.

    Example:
        status = get_fleet_status(client)
        for name, state in status.items():
            print(f"{name}: alt={state['z_agl']:.1f}m")
    """
    from drone import primitives as prim

    original = client.active_drone_name
    status: dict = {}

    for name in client.get_active_drone_names():
        client.set_active_drone(name)
        status[name] = prim.get_state(client)

    # Restore original selection
    client.set_active_drone(original)
    logger.info("get_fleet_status → %d drones", len(status))
    return status
