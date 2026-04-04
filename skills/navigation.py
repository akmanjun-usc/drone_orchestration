"""
Navigation skills.

These are the functions Claude generates calls to.
Every function is documented so the docstring can be
injected verbatim into the GSCE system prompt (Phase 3).
"""

import math
import time
import logging

from drone.bridge import DroneClient
from drone import primitives as prim

logger = logging.getLogger(__name__)


def fly_to(
    client: DroneClient,
    x: float,
    y: float,
    altitude_m: float,
    speed_ms: float = 5.0,
) -> None:
    """
    Fly to an absolute position in the simulation world frame.

    Args:
        client: Connected DroneClient.
        x: North position in metres from spawn point.
        y: East position in metres from spawn point.
        altitude_m: Target altitude in metres AGL (positive number).
        speed_ms: Travel speed in m/s (default 5.0, max 15.0).

    Example:
        fly_to(client, x=20, y=10, altitude_m=10)
    """
    logger.info("fly_to  x=%.1f  y=%.1f  alt=%.1f m  speed=%.1f m/s", x, y, altitude_m, speed_ms)
    prim.move_to_position(client, x=x, y=y, z_agl=altitude_m, speed_ms=speed_ms)


def hover(client: DroneClient, duration_s: float) -> None:
    """
    Hold current position for a fixed duration.

    Args:
        client: Connected DroneClient.
        duration_s: Time to hover in seconds.

    Example:
        hover(client, duration_s=5)
    """
    logger.info("hover  duration=%.1f s", duration_s)
    prim.hover(client, duration_s=duration_s)


def fly_path(
    client: DroneClient,
    waypoints: list[dict],
    altitude_m: float,
    speed_ms: float = 5.0,
) -> None:
    """
    Fly through an ordered list of (x, y) waypoints at a fixed altitude.

    Args:
        client: Connected DroneClient.
        waypoints: List of dicts, each with keys 'x' and 'y' (metres).
        altitude_m: Constant altitude in metres AGL for all waypoints.
        speed_ms: Travel speed in m/s (default 5.0).

    Example:
        fly_path(client, waypoints=[{"x": 0, "y": 0}, {"x": 10, "y": 10}], altitude_m=8)
    """
    logger.info("fly_path  %d waypoints  alt=%.1f m", len(waypoints), altitude_m)
    for wp in waypoints:
        prim.move_to_position(client, x=wp["x"], y=wp["y"], z_agl=altitude_m, speed_ms=speed_ms)


def orbit_point(
    client: DroneClient,
    cx: float,
    cy: float,
    radius_m: float,
    altitude_m: float,
    speed_ms: float = 3.0,
    num_points: int = 16,
) -> None:
    """
    Orbit a ground point in a horizontal circle.

    Args:
        client: Connected DroneClient.
        cx: North coordinate of orbit centre in metres.
        cy: East coordinate of orbit centre in metres.
        radius_m: Orbit radius in metres.
        altitude_m: Altitude in metres AGL for the whole orbit.
        speed_ms: Travel speed in m/s (default 3.0).
        num_points: Number of waypoints used to approximate the circle (default 16).

    Example:
        orbit_point(client, cx=0, cy=0, radius_m=15, altitude_m=12)
    """
    logger.info(
        "orbit_point  centre=(%.1f, %.1f)  r=%.1f m  alt=%.1f m",
        cx, cy, radius_m, altitude_m,
    )
    for i in range(num_points + 1):
        angle = 2 * math.pi * i / num_points
        wx = cx + radius_m * math.cos(angle)
        wy = cy + radius_m * math.sin(angle)
        prim.move_to_position(client, x=wx, y=wy, z_agl=altitude_m, speed_ms=speed_ms)


def return_home(client: DroneClient) -> None:
    """
    Fly back to the spawn position and land.

    Args:
        client: Connected DroneClient.

    Example:
        return_home(client)
    """
    logger.info("return_home")
    prim.return_to_home(client)
