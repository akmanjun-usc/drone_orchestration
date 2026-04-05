"""
Simulation configuration for Project AirSim.

Key facts from the official examples:
  - ProjectAirSimClient() takes NO constructor arguments.
    Connection address and ports are handled by the projectairsim
    library internally, not from Python.
  - Scene config files are looked up by filename only.
    They must live in a sim_config/ folder next to your script.
  - vehicle_name must match the "name" field in the scene config.

Multi-drone notes:
  - scene_multi_drone.jsonc pre-defines 10 drones (Drone1–Drone10).
  - Only `initial_active_drones` are armed on connect; the rest
    are idle until spawn_drone() is called.
  - ALL_DRONE_NAMES lists every drone declared in the scene config.
"""

from dataclasses import dataclass, field


# Canonical list of every drone name in scene_multi_drone.jsonc.
ALL_DRONE_NAMES: list[str] = [f"Drone{i}" for i in range(1, 11)]
MAX_DRONES: int = 10


@dataclass
class SimConfig:
    # Scene config filename (no path). Must exist in sim_config/ subfolder.
    scene_config: str = "scene_multi_drone.jsonc"

    # Primary drone name — the first drone activated on connect.
    vehicle_name: str = "Drone1"

    # How many drones to activate automatically when the scene loads.
    # 1 = only Drone1 is armed; additional drones are spawned on demand.
    initial_active_drones: int = 1

    # Maximum simultaneous active drones (must match scene config).
    max_drones: int = MAX_DRONES

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
