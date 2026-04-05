"""
Drone primitives for Project AirSim.

Verified against the official example scripts from example_user_scripts.zip.

Key confirmed facts:
  - drone.get_ground_truth_kinematics() returns a dict:
      ["pose"]["position"]    -> {"x", "y", "z"}  (NED metres, z negative = up)
      ["pose"]["orientation"] -> {"w", "x", "y", "z"} quaternion
      ["twist"]["linear"]     -> {"x", "y", "z"}  (NED m/s)
  - drone.go_home_async(velocity) exists (confirmed in move_apis.py)
  - Camera data comes only via subscriptions, not pull calls
  - All async calls need the double-await via client.run_async()
  - from projectairsim.utils import quaternion_to_rpy is available
"""

import math
import time
import logging

from projectairsim.utils import quaternion_to_rpy

from drone.bridge import DroneClient
from drone.config import SIM_CONFIG

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Flight control
# ------------------------------------------------------------------

def takeoff(client: DroneClient, altitude_m: float | None = None) -> None:
    """
    Take off and climb to hover altitude.

    Args:
        client: Connected DroneClient.
        altitude_m: Target altitude in metres AGL (positive). Defaults to config value.
    """
    alt = altitude_m if altitude_m is not None else SIM_CONFIG.takeoff_altitude_m
    logger.info("Taking off to %.1f m AGL", alt)

    # takeoff_async lifts to a safe default height (~3 m)
    client.run_async(lambda: client.drone.takeoff_async())

    # Climb to requested altitude if higher than default takeoff height
    current_alt = get_altitude(client)
    if alt - current_alt > 0.5:
        climb_duration = (alt - current_alt) / SIM_CONFIG.default_speed_ms + 1.0
        # Capture to avoid late-binding in lambda
        _dur = climb_duration
        _spd = SIM_CONFIG.default_speed_ms
        client.run_async(
            lambda: client.drone.move_by_velocity_async(
                v_north=0.0, v_east=0.0, v_down=-_spd, duration=_dur
            )
        )

    # Zero velocity to stabilise
    client.run_async(
        lambda: client.drone.move_by_velocity_async(
            v_north=0.0, v_east=0.0, v_down=0.0, duration=1.0
        )
    )
    logger.info("Hover reached at %.1f m AGL", alt)


def land(client: DroneClient) -> None:
    """
    Land at the current XY position.

    Args:
        client: Connected DroneClient.
    """
    logger.info("Landing...")
    client.run_async(lambda: client.drone.land_async())
    logger.info("Landed.")


def hover(client: DroneClient, duration_s: float = 2.0) -> None:
    """
    Hold position for a given number of seconds.

    Args:
        client: Connected DroneClient.
        duration_s: How long to hover in seconds.
    """
    logger.info("Hovering for %.1f s", duration_s)
    _dur = duration_s
    client.run_async(
        lambda: client.drone.move_by_velocity_async(
            v_north=0.0, v_east=0.0, v_down=0.0, duration=_dur
        )
    )


def move_to_position(
    client: DroneClient,
    x: float,
    y: float,
    z_agl: float,
    speed_ms: float | None = None,
) -> None:
    """
    Fly to an absolute NED position.

    Args:
        client: Connected DroneClient.
        x: North offset in metres from spawn point.
        y: East offset in metres from spawn point.
        z_agl: Altitude in metres AGL (positive = up, converted to NED internally).
        speed_ms: Travel speed in m/s. Defaults to config default.
    """
    speed = speed_ms or SIM_CONFIG.default_speed_ms
    ned_z = -z_agl  # NED: negative Z is up
    logger.info(
        "move_to_position  x=%.1f  y=%.1f  alt=%.1f m  speed=%.1f m/s",
        x, y, z_agl, speed,
    )
    # Capture all variables before the lambda to avoid late binding
    _x, _y, _z, _s = x, y, ned_z, speed
    client.run_async(
        lambda: client.drone.move_to_position_async(
            north=_x, east=_y, down=_z, velocity=_s
        )
    )


def move_by_velocity(
    client: DroneClient,
    vx: float,
    vy: float,
    vz: float,
    duration_s: float,
) -> None:
    """
    Fly with a fixed velocity vector for a set duration.

    Args:
        client: Connected DroneClient.
        vx: North velocity in m/s.
        vy: East velocity in m/s.
        vz: Vertical velocity in m/s (positive = up, converted to NED internally).
        duration_s: Duration in seconds.
    """
    logger.info(
        "move_by_velocity  vx=%.1f  vy=%.1f  vz=%.1f  duration=%.1f s",
        vx, vy, vz, duration_s,
    )
    _vn, _ve, _vd, _dur = vx, vy, -vz, duration_s
    client.run_async(
        lambda: client.drone.move_by_velocity_async(
            v_north=_vn, v_east=_ve, v_down=_vd, duration=_dur
        )
    )


def rotate_to_yaw(client: DroneClient, yaw_deg: float, margin_deg: float = 5.0) -> None:
    """
    Rotate to an absolute yaw angle.

    Args:
        client: Connected DroneClient.
        yaw_deg: Target yaw in degrees (0 = North, 90 = East).
        margin_deg: Kept for API compatibility with original AirSim version.
    """
    yaw_rad = math.radians(yaw_deg)
    logger.info("rotate_to_yaw  %.1f deg  (%.4f rad)", yaw_deg, yaw_rad)
    _yaw = yaw_rad
    client.run_async(lambda: client.drone.rotate_to_yaw_async(yaw=_yaw))


def return_to_home(client: DroneClient) -> None:
    """
    Fly back to the home/spawn position and land.

    Uses go_home_async which is confirmed in move_apis.py.

    Args:
        client: Connected DroneClient.
    """
    logger.info("Returning home...")
    _spd = SIM_CONFIG.default_speed_ms
    client.run_async(lambda: client.drone.go_home_async(velocity=_spd))
    client.run_async(lambda: client.drone.land_async())
    logger.info("Home reached.")


# ------------------------------------------------------------------
# State / telemetry
# ------------------------------------------------------------------

def get_state(client: DroneClient) -> dict:
    """
    Return current drone state as a plain dict.

    Calls drone.get_ground_truth_kinematics() which is a synchronous
    pull call confirmed in wind.py, px4_mission.py, and others.

    Returns a dict with keys:
        x, y, z_agl   position in metres. z_agl positive = up.
        vx, vy, vz    velocity in m/s. vz positive = up.
        roll, pitch, yaw  orientation in degrees.
        is_landed     True if z_agl is below 0.3 m.
    """
    kin = client.drone.get_ground_truth_kinematics()

    pos = kin["pose"]["position"]       # {"x", "y", "z"} NED metres
    ori = kin["pose"]["orientation"]    # {"w", "x", "y", "z"} quaternion
    vel = kin["twist"]["linear"]        # {"x", "y", "z"} NED m/s

    # quaternion_to_rpy is confirmed importable from projectairsim.utils
    roll_rad, pitch_rad, yaw_rad = quaternion_to_rpy(
        ori["w"], ori["x"], ori["y"], ori["z"]
    )

    z_agl = -pos["z"]  # NED: negative Z is up, flip to positive AGL

    return {
        "x": pos["x"],
        "y": pos["y"],
        "z_agl": z_agl,
        "vx": vel["x"],
        "vy": vel["y"],
        "vz": -vel["z"],                 # flip NED Z to up-positive
        "roll": math.degrees(roll_rad),
        "pitch": math.degrees(pitch_rad),
        "yaw": math.degrees(yaw_rad),
        "is_landed": z_agl < 0.3,       # no pull API for landed state, infer from altitude
    }


def get_altitude(client: DroneClient) -> float:
    """
    Return current altitude in metres AGL.

    Args:
        client: Connected DroneClient.
    """
    return get_state(client)["z_agl"]


def get_gps(client: DroneClient) -> dict:
    """
    Return GPS position via subscription callback.

    Note: GPS sensor must be enabled in your robot config JSONC
    ("enabled": true) for this to return data.

    Args:
        client: Connected DroneClient.

    Returns:
        Dict with keys: latitude, longitude, altitude_msl.
        Returns zeros if no GPS data has arrived yet.
    """
    gps_data = client.get_latest_image("GPS/gps")
    if gps_data is None:
        client.subscribe_camera(
            sensor_name="GPS",
            image_key="GPS/gps",
            topic_key="gps",
        )
        time.sleep(0.3)
        gps_data = client.get_latest_image("GPS/gps")

    if gps_data is None:
        return {"latitude": 0.0, "longitude": 0.0, "altitude_msl": 0.0}

    return {
        "latitude": gps_data.get("latitude", 0.0),
        "longitude": gps_data.get("longitude", 0.0),
        "altitude_msl": gps_data.get("altitude", 0.0),
    }


# ------------------------------------------------------------------
# Camera / perception
# ------------------------------------------------------------------

def capture_image(
    client: DroneClient,
    camera_name: str = "DownCamera",
    topic_key: str = "scene_camera",
    save_path: str | None = None,
) -> bytes:
    """
    Return the latest frame from a subscribed camera.

    Camera names and topic keys come from your robot config JSONC.
    The default robot_quadrotor_fastphysics.jsonc defines:
        sensors["Chase"]["scene_camera"]
        sensors["DownCamera"]["scene_camera"]
        sensors["DownCamera"]["depth_camera"]

    On first call for a new camera, this subscribes automatically
    and waits 0.5 s for the first frame to arrive.

    Args:
        client: Connected DroneClient.
        camera_name: Sensor ID from your robot config, e.g. "DownCamera".
        topic_key: Topic key, e.g. "scene_camera" or "depth_camera".
        save_path: If given, write bytes to this file path.

    Returns:
        Raw image bytes.

    Raises:
        RuntimeError if no frame has arrived yet.
    """
    image_key = f"{camera_name}/{topic_key}"

    if image_key not in client._latest_images:
        client.subscribe_camera(
            sensor_name=camera_name,
            image_key=image_key,
            topic_key=topic_key,
        )
        time.sleep(0.5)

    data = client.get_latest_image(image_key)
    if data is None:
        raise RuntimeError(
            f"No image received from sensors['{camera_name}']['{topic_key}']. "
            f"Check that this sensor is defined and enabled in your robot config JSONC."
        )

    if save_path:
        with open(save_path, "wb") as f:
            f.write(data)
        logger.info("Image saved to %s", save_path)

    return data


def get_lidar(client: DroneClient, lidar_name: str = "LidarSensor") -> list[dict]:
    """
    Return a LIDAR point cloud snapshot.

    Args:
        client: Connected DroneClient.
        lidar_name: Sensor ID from your robot config JSONC.

    Returns:
        List of dicts with keys x, y, z in metres.
    """
    data = client.get_latest_image(f"{lidar_name}/lidar_pc")
    if data is None:
        client.subscribe_camera(
            sensor_name=lidar_name,
            image_key=f"{lidar_name}/lidar_pc",
            topic_key="lidar_pc",
        )
        time.sleep(0.3)
        data = client.get_latest_image(f"{lidar_name}/lidar_pc")

    if data is None:
        return []

    # data is a list of [x, y, z] triples
    points = []
    if isinstance(data, list):
        for pt in data:
            if isinstance(pt, (list, tuple)) and len(pt) >= 3:
                points.append({"x": pt[0], "y": pt[1], "z": pt[2]})
    return points
