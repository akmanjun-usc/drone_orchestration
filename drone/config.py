"""
Simulation configuration for Project AirSim.

Key facts from the official examples:
  - ProjectAirSimClient() takes NO constructor arguments.
    Connection address and ports are handled by the projectairsim
    library internally, not from Python.
  - Scene config files are looked up by filename only.
    They must live in a sim_config/ folder next to your script.
  - vehicle_name must match the "name" field in scene_basic_drone.jsonc.
"""

from dataclasses import dataclass


@dataclass
class SimConfig:
    # Scene config filename (no path). Must exist in sim_config/ subfolder.
    # The default matches the official hello_drone.py example.
    scene_config: str = "scene_basic_drone.jsonc"

    # Drone name — must match the "name" field in your scene config.
    vehicle_name: str = "Drone1"

    # Seconds to wait after the scene loads before sending commands.
    scene_load_delay_s: float = 2.0

    # Flight defaults
    default_speed_ms: float = 5.0
    takeoff_altitude_m: float = 3.0  # positive AGL (converted to NED internally)

    # Safety limits — used by the GSCE constraints prompt section.
    max_altitude_m: float = 50.0
    max_speed_ms: float = 15.0
    min_battery_pct: float = 20.0


# Module-level singleton — import this everywhere.
SIM_CONFIG = SimConfig()
