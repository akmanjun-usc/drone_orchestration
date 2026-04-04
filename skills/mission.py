"""
Mission skills.

Higher-level compound behaviours built from navigation
and perception primitives. These are the most complex
skills Claude can invoke in generated code.
"""

import logging

from drone.bridge import DroneClient
from skills.navigation import fly_to, fly_path, hover
from skills.perception import capture_image, get_state

logger = logging.getLogger(__name__)


def survey_grid(
    client: DroneClient,
    origin_x: float,
    origin_y: float,
    width_m: float,
    height_m: float,
    altitude_m: float,
    row_spacing_m: float = 10.0,
    speed_ms: float = 5.0,
    capture_photos: bool = True,
    photo_dir: str = "survey_photos",
) -> list[bytes]:
    """
    Perform a lawn-mower grid survey over a rectangular area.

    Flies parallel rows spaced row_spacing_m apart, optionally
    capturing a photo at the start of each row.

    Args:
        client: Connected DroneClient.
        origin_x: North coordinate of the survey area corner (metres).
        origin_y: East coordinate of the survey area corner (metres).
        width_m: Survey area width along the Y (east) axis in metres.
        height_m: Survey area height along the X (north) axis in metres.
        altitude_m: Survey altitude in metres AGL.
        row_spacing_m: Distance between parallel rows in metres (default 10).
        speed_ms: Flight speed in m/s (default 5.0).
        capture_photos: If True, capture a photo at each row start.
        photo_dir: Directory to save photos when capture_photos is True.

    Returns:
        List of PNG bytes for each captured photo (empty if capture_photos=False).

    Example:
        photos = survey_grid(
            client,
            origin_x=0, origin_y=0,
            width_m=50, height_m=50,
            altitude_m=20,
        )
        print(f"Survey complete, {len(photos)} photos taken")
    """
    import os
    import math

    os.makedirs(photo_dir, exist_ok=True)
    photos = []
    num_rows = max(1, int(math.ceil(height_m / row_spacing_m)) + 1)

    logger.info(
        "survey_grid  origin=(%.1f,%.1f)  %.0fx%.0f m  %d rows  alt=%.1f m",
        origin_x, origin_y, width_m, height_m, num_rows, altitude_m,
    )

    fly_to(client, x=origin_x, y=origin_y, altitude_m=altitude_m, speed_ms=speed_ms)

    for row in range(num_rows):
        row_x = origin_x + row * row_spacing_m
        if row_x > origin_x + height_m:
            row_x = origin_x + height_m

        # Alternate row direction (boustrophedon / lawn-mower)
        if row % 2 == 0:
            start_y, end_y = origin_y, origin_y + width_m
        else:
            start_y, end_y = origin_y + width_m, origin_y

        fly_to(client, x=row_x, y=start_y, altitude_m=altitude_m, speed_ms=speed_ms)

        if capture_photos:
            path = os.path.join(photo_dir, f"row_{row:03d}_start.png")
            img = capture_image(client, save_path=path)
            photos.append(img)

        fly_to(client, x=row_x, y=end_y, altitude_m=altitude_m, speed_ms=speed_ms)

    logger.info("survey_grid complete, %d photos captured", len(photos))
    return photos


def search_area(
    client: DroneClient,
    center_x: float,
    center_y: float,
    radius_m: float,
    altitude_m: float,
    speed_ms: float = 4.0,
) -> list[bytes]:
    """
    Search a circular area using an expanding spiral pattern.

    Starts at the centre and spirals outward, capturing a photo
    at each spiral vertex.

    Args:
        client: Connected DroneClient.
        center_x: North coordinate of search centre (metres).
        center_y: East coordinate of search centre (metres).
        radius_m: Maximum search radius in metres.
        altitude_m: Search altitude in metres AGL.
        speed_ms: Flight speed in m/s (default 4.0).

    Returns:
        List of PNG bytes captured along the spiral.

    Example:
        photos = search_area(client, center_x=0, center_y=0, radius_m=30, altitude_m=15)
        print(f"Search done, {len(photos)} images")
    """
    import math

    logger.info(
        "search_area  centre=(%.1f,%.1f)  r=%.1f m  alt=%.1f m",
        center_x, center_y, radius_m, altitude_m,
    )

    fly_to(client, x=center_x, y=center_y, altitude_m=altitude_m, speed_ms=speed_ms)

    photos = []
    img = capture_image(client)
    photos.append(img)

    rings = max(1, int(radius_m / 10))
    for ring in range(1, rings + 1):
        r = ring * (radius_m / rings)
        num_pts = max(8, ring * 8)
        for i in range(num_pts):
            angle = 2 * math.pi * i / num_pts
            wx = center_x + r * math.cos(angle)
            wy = center_y + r * math.sin(angle)
            fly_to(client, x=wx, y=wy, altitude_m=altitude_m, speed_ms=speed_ms)

        img = capture_image(client)
        photos.append(img)

    logger.info("search_area complete, %d images", len(photos))
    return photos


def inspect_point(
    client: DroneClient,
    target_x: float,
    target_y: float,
    standoff_m: float = 10.0,
    altitude_m: float = 10.0,
    num_angles: int = 4,
) -> list[bytes]:
    """
    Inspect a ground point from multiple angles at a fixed standoff distance.

    Positions the drone at evenly-spaced angles around the target
    and captures a photo at each position.

    Args:
        client: Connected DroneClient.
        target_x: North coordinate of the inspection target (metres).
        target_y: East coordinate of the inspection target (metres).
        standoff_m: Distance from the target to hover at (metres).
        altitude_m: Altitude in metres AGL for all inspection positions.
        num_angles: Number of viewing angles (default 4 = N/S/E/W).

    Returns:
        List of PNG bytes, one per angle.

    Example:
        photos = inspect_point(client, target_x=30, target_y=20, standoff_m=8, num_angles=6)
        print(f"Inspection done, {len(photos)} photos")
    """
    import math

    logger.info(
        "inspect_point  target=(%.1f,%.1f)  standoff=%.1f m  %d angles",
        target_x, target_y, standoff_m, num_angles,
    )

    photos = []
    for i in range(num_angles):
        angle = 2 * math.pi * i / num_angles
        px = target_x + standoff_m * math.cos(angle)
        py = target_y + standoff_m * math.sin(angle)
        fly_to(client, x=px, y=py, altitude_m=altitude_m)
        hover(client, duration_s=1.0)
        img = capture_image(client)
        photos.append(img)

    logger.info("inspect_point complete, %d photos", len(photos))
    return photos
