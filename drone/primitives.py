"""
Drone primitives — the only place that calls AirSim APIs.

Every function takes a DroneClient as its first argument.
Return types are plain Python dicts or scalars so the rest
of the project never needs to import airsim.
"""

import logging
import airsim

from drone.bridge import DroneClient
from drone.config import SIM_CONFIG

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Flight control
# ------------------------------------------------------------------

def takeoff(client: DroneClient, altitude_m: float | None = None) -> None:
    """
    Arm and take off to hover altitude.

    Args:
        client: Connected DroneClient.
        altitude_m: Target hover altitude in metres AGL (positive number).
                    Defaults to config.takeoff_altitude_m.
    """
    alt = altitude_m if altitude_m is not None else abs(SIM_CONFIG.takeoff_altitude_m)
    ned_z = -alt  # AirSim NED: negative Z = up

    logger.info("Taking off to %.1f m AGL", alt)
    client.client.takeoffAsync(vehicle_name=client.vehicle).join()
    client.client.moveToZAsync(
        ned_z,
        velocity=SIM_CONFIG.default_speed_ms,
        vehicle_name=client.vehicle,
    ).join()
    logger.info("Hover reached at %.1f m AGL", alt)


def land(client: DroneClient) -> None:
    """
    Land and disarm at the current XY position.

    Args:
        client: Connected DroneClient.
    """
    logger.info("Landing...")
    client.client.landAsync(vehicle_name=client.vehicle).join()
    logger.info("Landed.")


def hover(client: DroneClient, duration_s: float = 2.0) -> None:
    """
    Hold position for a given number of seconds.

    Args:
        client: Connected DroneClient.
        duration_s: How long to hover in seconds.
    """
    logger.info("Hovering for %.1f s", duration_s)
    client.client.hoverAsync(vehicle_name=client.vehicle).join()
    import time
    time.sleep(duration_s)


def move_to_position(
    client: DroneClient,
    x: float,
    y: float,
    z_agl: float,
    speed_ms: float | None = None,
) -> None:
    """
    Fly to an absolute NED position (AirSim world frame).

    Args:
        client: Connected DroneClient.
        x: North offset in metres from spawn point.
        y: East offset in metres from spawn point.
        z_agl: Altitude in metres AGL (positive number, converted to NED internally).
        speed_ms: Travel speed in m/s. Defaults to config default.
    """
    speed = speed_ms or SIM_CONFIG.default_speed_ms
    ned_z = -z_agl
    logger.info("Moving to (%.1f, %.1f) at %.1f m AGL, speed=%.1f m/s", x, y, z_agl, speed)
    client.client.moveToPositionAsync(
        x, y, ned_z,
        velocity=speed,
        vehicle_name=client.vehicle,
    ).join()


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
        vz: Vertical velocity in m/s (positive = down in NED; use negative to climb).
        duration_s: How long to apply the velocity.
    """
    logger.info(
        "Velocity move: vx=%.1f vy=%.1f vz=%.1f for %.1f s", vx, vy, vz, duration_s
    )
    client.client.moveByVelocityAsync(
        vx, vy, vz,
        duration_s,
        vehicle_name=client.vehicle,
    ).join()


def rotate_to_yaw(client: DroneClient, yaw_deg: float, margin_deg: float = 5.0) -> None:
    """
    Rotate the drone to an absolute yaw angle.

    Args:
        client: Connected DroneClient.
        yaw_deg: Target yaw in degrees (0 = North, 90 = East).
        margin_deg: Acceptable yaw error in degrees.
    """
    logger.info("Rotating to yaw=%.1f°", yaw_deg)
    client.client.rotateToYawAsync(
        yaw_deg,
        margin=margin_deg,
        vehicle_name=client.vehicle,
    ).join()


def return_to_home(client: DroneClient) -> None:
    """
    Fly back to the spawn/home position and land.

    Args:
        client: Connected DroneClient.
    """
    logger.info("Returning to home position...")
    client.client.goHomeAsync(vehicle_name=client.vehicle).join()
    logger.info("Home reached.")


# ------------------------------------------------------------------
# State / telemetry
# ------------------------------------------------------------------

def get_state(client: DroneClient) -> dict:
    """
    Return current drone state as a plain dict.

    Returns:
        Dict with keys:
            x, y, z_agl   -- position in metres (z_agl is positive = up)
            vx, vy, vz     -- velocity in m/s
            roll, pitch, yaw -- orientation in degrees
            is_landed      -- bool
            timestamp      -- simulation timestamp in ns
    """
    state = client.client.getMultirotorState(vehicle_name=client.vehicle)
    pos = state.kinematics_estimated.position
    vel = state.kinematics_estimated.linear_velocity
    ang = airsim.to_eularian_angles(state.kinematics_estimated.orientation)

    return {
        "x": pos.x_val,
        "y": pos.y_val,
        "z_agl": -pos.z_val,          # convert NED Z to AGL
        "vx": vel.x_val,
        "vy": vel.y_val,
        "vz": -vel.z_val,             # positive = up
        "roll": float(airsim.utils.to_eularian_angles(
            state.kinematics_estimated.orientation)[0]) * 57.2958,
        "pitch": float(ang[1]) * 57.2958,
        "yaw": float(ang[2]) * 57.2958,
        "is_landed": state.landed_state == airsim.LandedState.Landed,
        "timestamp": state.timestamp,
    }


def get_altitude(client: DroneClient) -> float:
    """
    Return current altitude in metres AGL.

    Args:
        client: Connected DroneClient.

    Returns:
        Altitude as a positive float in metres.
    """
    return get_state(client)["z_agl"]


def get_gps(client: DroneClient) -> dict:
    """
    Return GPS position (latitude, longitude, altitude MSL).

    Args:
        client: Connected DroneClient.

    Returns:
        Dict with keys: latitude, longitude, altitude_msl.
    """
    gps = client.client.getGpsData(vehicle_name=client.vehicle)
    return {
        "latitude": gps.gnss.geo_point.latitude,
        "longitude": gps.gnss.geo_point.longitude,
        "altitude_msl": gps.gnss.geo_point.altitude,
    }


# ------------------------------------------------------------------
# Sensors / perception
# ------------------------------------------------------------------

def capture_image(
    client: DroneClient,
    camera_name: str = "0",
    image_type: str = "scene",
) -> bytes:
    """
    Capture a PNG image from the specified camera.

    Args:
        client: Connected DroneClient.
        camera_name: AirSim camera name or index string.
        image_type: "scene" (RGB), "depth_planar", or "segmentation".

    Returns:
        Raw PNG bytes. Write to a file or pass to a vision model.
    """
    type_map = {
        "scene": airsim.ImageType.Scene,
        "depth_planar": airsim.ImageType.DepthPlanar,
        "segmentation": airsim.ImageType.Segmentation,
    }
    img_type = type_map.get(image_type, airsim.ImageType.Scene)

    responses = client.client.simGetImages(
        [airsim.ImageRequest(camera_name, img_type, False, True)],
        vehicle_name=client.vehicle,
    )

    if not responses:
        raise RuntimeError(f"No image returned from camera '{camera_name}'")

    return responses[0].image_data_uint8


def get_lidar(client: DroneClient, lidar_name: str = "LidarSensor1") -> list[dict]:
    """
    Return LIDAR point cloud as a list of (x, y, z) dicts.

    Args:
        client: Connected DroneClient.
        lidar_name: Name of the LIDAR sensor in AirSim settings.

    Returns:
        List of dicts with keys x, y, z in metres (AirSim world frame).
    """
    data = client.client.getLidarData(
        lidar_name=lidar_name,
        vehicle_name=client.vehicle,
    )
    points = []
    for i in range(0, len(data.point_cloud), 3):
        points.append({
            "x": data.point_cloud[i],
            "y": data.point_cloud[i + 1],
            "z": data.point_cloud[i + 2],
        })
    return points
