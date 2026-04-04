"""
Simulation and connection configuration for Project AirSim.

Project AirSim uses two ports (topics and services) instead of
the single port used by the original AirSim.
"""

from dataclasses import dataclass


@dataclass
class SimConfig:
    # Project AirSim connection
    host: str = "127.0.0.1"
    port_topics: int = 4760       # pub/sub topic port
    port_services: int = 4761     # request/response service port

    # Scene config file (JSONC) that Project AirSim loads
    # Place this file in your Unreal project's Config folder
    scene_config: str = "scene_basic_drone.jsonc"

    # Which drone to control (must match robot name in scene config)
    vehicle_name: str = "Drone1"

    # How long to wait after scene loads before sending commands (seconds)
    scene_load_delay_s: float = 2.0

    # Physics — all values in SI units (metres, radians)
    default_speed_ms: float = 5.0
    takeoff_altitude_m: float = 3.0   # positive = up (converted to NED internally)

    # Safety limits enforced by the GSCE constraints layer
    max_altitude_m: float = 50.0
    max_speed_ms: float = 15.0
    min_battery_pct: float = 20.0

    # Timeouts
    connection_timeout_s: float = 5.0
    command_timeout_s: float = 30.0


# Module-level singleton — import this everywhere
SIM_CONFIG = SimConfig()
