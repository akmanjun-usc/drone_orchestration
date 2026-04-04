"""
Drone primitives for Project AirSim.

Same function names and signatures as the original AirSim primitives.py.
Only the internals change to use the Project AirSim Drone API.

Key differences from original AirSim:
  - All movement calls are async. client.run() bridges to synchronous.
  - Units are SI: metres and RADIANS (not degrees for angles).
  - NED convention still applies: negative Z = up.
  - State data comes from subscribed topics, not a direct get call.
  - Camera images use get_images() with a different request structure.
"""

import math
import time
import logging

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
        altitude_m: Target hover altitude in metres AGL (positive number).
                    Defaults to config.takeoff_altitude_m.
    """
    alt = altitude_m if altitude_m is not None else SIM_CONFIG.takeoff_altitude_m
    logger.info("Taking off to %.1f m AGL", alt)

    # takeoff_async climbs to a default safe height
    client.run(client.drone.takeoff_async())

    # Then move to the requested altitude using velocity control
    # v_down is negative to climb in NED
    ned_climb_speed = -SIM_CONFIG.default_speed_ms
    current_alt = get_altitude(client)
    climb_duration = abs(alt - current_alt) / SIM_CONFIG.default_speed_ms + 1.0

    client.run(
        client.drone.move_by_velocity_async(
            v_north=0.0,
            v_east=0.0,
            v_down=ned_climb_speed,
            duration=climb_duration,
        )
    )
    # Hover to stabilise
    client.run(client.drone.move_by_velocity_async(
        v_north=0.0, v_east=0.0, v_down=0.0, duration=1.0
    ))
    logger.info("Hover reached at %.1f m AGL", alt)


def land(client: DroneClient) -> None:
    """
    Land at the current XY position.

    Args:
        client: Connected DroneClient.
    """
    logger.info("Landing...")
    client.run(client.drone.land_async())
    logger.info("Landed.")


def hover(client: DroneClient, duration_s: float = 2.0) -> None:
    """
    Hold position for a given number of seconds.

    Args:
        client: Connected DroneClient.
        duration_s: How long to hover in seconds.
    """
    logger.info("Hovering for %.1f s", duration_s)
    # Zero velocity for the requested duration holds position
    client.run(
        client.drone.move_by_velocity_async(
            v_north=0.0,
            v_east=0.0,
            v_down=0.0,
            duration=duration_s,
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

    # Project AirSim: move_to_position_async takes NED x, y, z and speed
    client.run(
        client.drone.move_to_position_async(
            north=x,
            east=y,
            down=ned_z,
            velocity=speed,
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
        vz: Vertical velocity in m/s (positive = up; converted to NED down internally).
        duration_s: How long to apply the velocity.
    """
    logger.info(
        "move_by_velocity  vx=%.1f  vy=%.1f  vz=%.1f  duration=%.1f s",
        vx, vy, vz, duration_s,
    )
    client.run(
        client.drone.move_by_velocity_async(
            v_north=vx,
            v_east=vy,
            v_down=-vz,   # convert: positive up -> negative NED down
            duration=duration_s,
        )
    )


def rotate_to_yaw(client: DroneClient, yaw_deg: float, margin_deg: float = 5.0) -> None:
    """
    Rotate to an absolute yaw angle.

    Args:
        client: Connected DroneClient.
        yaw_deg: Target yaw in degrees (0 = North, 90 = East).
        margin_deg: Acceptable yaw error in degrees (unused in Project AirSim,
                    kept for API compatibility).
    """
    yaw_rad = math.radians(yaw_deg)
    logger.info("rotate_to_yaw  yaw=%.1f°  (%.4f rad)", yaw_deg, yaw_rad)

    # Project AirSim uses rotate_to_yaw_async with radians
    client.run(
        client.drone.rotate_to_yaw_async(yaw=yaw_rad)
    )


def return_to_home(client: DroneClient) -> None:
    """
    Fly back to the spawn/home position and land.

    Args:
        client: Connected DroneClient.
    """
    logger.info("Returning to home position...")
    # Fly to origin (0, 0) then land
    current_alt = get_altitude(client)
    move_to_position(client, x=0.0, y=0.0, z_agl=max(current_alt, 5.0))
    land(client)
    logger.info("Home reached.")


# ------------------------------------------------------------------
# State / telemetry
# ------------------------------------------------------------------

def get_state(client: DroneClient) -> dict:
    """
    Return current drone state as a plain dict.

    Returns:
        Dict with keys:
            x, y, z_agl   -- position in metres (z_agl positive = up)
            vx, vy, vz     -- velocity in m/s (vz positive = up)
            roll, pitch, yaw -- orientation in DEGREES
            is_landed      -- bool
    """
    state = client.drone.get_ground_truth_kinematics()
    pos = state.position        # NED metres
    vel = state.linear_velocity # NED m/s
    ori = state.orientation     # quaternion

    # Convert quaternion to Euler angles (radians) then to degrees
    roll_rad, pitch_rad, yaw_rad = _quat_to_euler(
        ori.w_val, ori.x_val, ori.y_val, ori.z_val
    )

    landed = client.drone.get_landed_state()

    return {
        "x": pos.x_val,
        "y": pos.y_val,
        "z_agl": -pos.z_val,              # NED Z to AGL
        "vx": vel.x_val,
        "vy": vel.y_val,
        "vz": -vel.z_val,                 # NED Z vel to up-positive
        "roll": math.degrees(roll_rad),
        "pitch": math.degrees(pitch_rad),
        "yaw": math.degrees(yaw_rad),
        "is_landed": landed,
    }


def get_altitude(client: DroneClient) -> float:
    """
    Return current altitude in metres AGL.

    Args:
        client: Connected DroneClient.

    Returns:
        Altitude as a positive float.
    """
    return get_state(client)["z_agl"]


def get_gps(client: DroneClient) -> dict:
    """
    Return GPS position.

    Args:
        client: Connected DroneClient.

    Returns:
        Dict with keys: latitude, longitude, altitude_msl.
    """
    gps = client.drone.get_gps_data()
    return {
        "latitude": gps.latitude,
        "longitude": gps.longitude,
        "altitude_msl": gps.altitude,
    }


# ------------------------------------------------------------------
# Sensors / perception
# ------------------------------------------------------------------

def capture_image(
    client: DroneClient,
    camera_name: str = "front_center",
    image_type: str = "scene",
) -> bytes:
    """
    Capture a PNG image from the specified camera.

    Args:
        client: Connected DroneClient.
        camera_name: Camera name as defined in your robot config JSONC.
                     Default is "front_center". In original AirSim this was "0".
        image_type: "scene" (RGB), "depth_planar", or "segmentation".

    Returns:
        Raw PNG bytes.
    """
    from projectairsim import ImageType

    type_map = {
        "scene": ImageType.Scene,
        "depth_planar": ImageType.DepthPlanar,
        "segmentation": ImageType.Segmentation,
    }
    img_type = type_map.get(image_type, ImageType.Scene)

    responses = client.drone.get_images(
        requests=[{"camera_name": camera_name, "image_type": img_type, "compress": True}]
    )

    if not responses:
        raise RuntimeError(f"No image returned from camera '{camera_name}'")

    return responses[0].image_data


def get_lidar(client: DroneClient, lidar_name: str = "lidar") -> list[dict]:
    """
    Return LIDAR point cloud as a list of (x, y, z) dicts.

    Args:
        client: Connected DroneClient.
        lidar_name: Sensor name as defined in your robot config JSONC.
                    In original AirSim this was "LidarSensor1".

    Returns:
        List of dicts with keys x, y, z in metres (world frame).
    """
    data = client.drone.get_lidar_data(lidar_name=lidar_name)
    points = []
    cloud = data.point_cloud
    for i in range(0, len(cloud), 3):
        points.append({
            "x": cloud[i],
            "y": cloud[i + 1],
            "z": cloud[i + 2],
        })
    return points


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _quat_to_euler(w: float, x: float, y: float, z: float) -> tuple:
    """Convert a unit quaternion to (roll, pitch, yaw) in radians."""
    # Roll (x-axis rotation)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # Pitch (y-axis rotation)
    sinp = 2.0 * (w * y - z * x)
    pitch = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1 else math.asin(sinp)

    # Yaw (z-axis rotation)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return roll, pitch, yaw
