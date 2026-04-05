"""skills — GSCE Skill API library."""

from skills.navigation import fly_to, orbit_point, hover, fly_path, return_home
from skills.perception import capture_image, get_altitude, get_state, get_lidar
from skills.mission import survey_grid, search_area, inspect_point
from skills.fleet import spawn_drone, list_drones, select_drone, get_active_drone, get_fleet_status

__all__ = [
    # Fleet management
    "spawn_drone", "list_drones", "select_drone", "get_active_drone", "get_fleet_status",
    # Navigation
    "fly_to", "orbit_point", "hover", "fly_path", "return_home",
    # Perception
    "capture_image", "get_altitude", "get_state", "get_lidar",
    # Mission
    "survey_grid", "search_area", "inspect_point",
]
