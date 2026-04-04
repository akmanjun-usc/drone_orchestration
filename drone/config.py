"""
Simulation and connection configuration.
Edit this file to match your AirSim / Unreal setup.
"""

from dataclasses import dataclass


@dataclass
class SimConfig:
    # AirSim connection
    host: str = "127.0.0.1"
    port: int = 41451

    # Which drone to control (matches Vehicles in settings.json)
    vehicle_name: str = "Drone1"

    # Physics
    default_speed_ms: float = 5.0       # m/s for movements
    default_altitude_m: float = -5.0    # NED: negative = up
    takeoff_altitude_m: float = -3.0    # NED hover height after takeoff

    # Safety limits (enforced by constraints layer in Phase 3)
    max_altitude_m: float = 50.0        # AGL metres
    max_speed_ms: float = 15.0
    min_battery_pct: float = 20.0

    # Timeouts
    connection_timeout_s: float = 5.0
    command_timeout_s: float = 30.0


# Module-level singleton — import this everywhere
SIM_CONFIG = SimConfig()
