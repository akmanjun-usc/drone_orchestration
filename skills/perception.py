"""
Perception skills.

Wraps drone/primitives sensor calls into documented functions
Claude can call from generated code.
"""

import logging

from drone.bridge import DroneClient
from drone import primitives as prim

logger = logging.getLogger(__name__)


def get_state(client: DroneClient) -> dict:
    """
    Return the current drone state.

    Args:
        client: Connected DroneClient.

    Returns:
        Dict with keys:
            x, y          -- position (metres, world frame)
            z_agl         -- altitude above ground in metres (positive = up)
            vx, vy, vz    -- velocity in m/s
            roll, pitch, yaw -- orientation in degrees
            is_landed     -- True if on the ground

    Example:
        state = get_state(client)
        print(state["z_agl"])
    """
    return prim.get_state(client)


def get_altitude(client: DroneClient) -> float:
    """
    Return current altitude in metres AGL.

    Args:
        client: Connected DroneClient.

    Returns:
        Altitude as a positive float (metres above ground).

    Example:
        alt = get_altitude(client)
        if alt < 5:
            fly_to(client, x=0, y=0, altitude_m=10)
    """
    return prim.get_altitude(client)


def capture_image(
    client: DroneClient,
    camera_name: str = "0",
    image_type: str = "scene",
    save_path: str | None = None,
) -> bytes:
    """
    Capture an image from the drone's onboard camera.

    Args:
        client: Connected DroneClient.
        camera_name: Camera identifier (default "0" = front camera).
        image_type: "scene" (RGB), "depth_planar", or "segmentation".
        save_path: If given, save the PNG to this file path.

    Returns:
        Raw PNG bytes.

    Example:
        img = capture_image(client, save_path="photo.png")
    """
    data = prim.capture_image(client, camera_name=camera_name, image_type=image_type)
    if save_path:
        with open(save_path, "wb") as f:
            f.write(data)
        logger.info("Image saved to %s", save_path)
    return data


def get_lidar(client: DroneClient, lidar_name: str = "LidarSensor1") -> list[dict]:
    """
    Return a LIDAR point cloud snapshot.

    Args:
        client: Connected DroneClient.
        lidar_name: Sensor name as defined in AirSim settings.json.

    Returns:
        List of dicts, each with keys 'x', 'y', 'z' in metres.

    Example:
        points = get_lidar(client)
        print(f"Got {len(points)} points")
    """
    return prim.get_lidar(client, lidar_name=lidar_name)


def detect_object(
    client: DroneClient,
    object_name_pattern: str,
) -> list[dict]:
    """
    Find objects in the scene whose name matches a pattern.

    Uses AirSim's built-in object detection (requires segmentation
    camera configured in settings.json).

    Args:
        client: Connected DroneClient.
        object_name_pattern: Wildcard pattern, e.g. "Car_*" or "Tree_01".

    Returns:
        List of dicts with keys:
            name      -- object name in Unreal
            x, y, z   -- object position in world frame (metres)

    Example:
        cars = detect_object(client, "Car_*")
        for car in cars:
            print(car["name"], car["x"], car["y"])
    """
    raw = client.client.simListSceneObjects(object_name_pattern)
    results = []
    for name in raw:
        pose = client.client.simGetObjectPose(name)
        results.append({
            "name": name,
            "x": pose.position.x_val,
            "y": pose.position.y_val,
            "z": -pose.position.z_val,  # convert NED to AGL
        })
    return results
