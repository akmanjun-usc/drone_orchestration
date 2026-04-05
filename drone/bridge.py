"""
Project AirSim connection bridge.

Verified against the official example scripts (hello_drone.py, move_apis.py,
sensors.py) from the UE5 example_user_scripts package.

Confirmed facts from the examples:
  1. ProjectAirSimClient() takes NO constructor arguments.
  2. Every async method returns a task that must be awaited TWICE:
       task = await drone.some_async()   # schedules
       await task                        # waits for completion
  3. Cameras are pub/sub via client.subscribe(drone.sensors[name][type], cb).
     There is no pull-based get_images() call.
  4. State comes from drone.get_ground_truth_kinematics() which returns a dict:
       ["pose"]["position"]  -> {"x": ..., "y": ..., "z": ...}   (NED metres)
       ["pose"]["orientation"] -> quaternion dict
       ["twist"]["linear"]   -> {"x": ..., "y": ..., "z": ...}   (NED m/s)
  5. go_home_async(velocity) exists and works correctly.
  6. Scene config files are looked up by filename only from a sim_config/ folder.
"""

import asyncio
import logging

from projectairsim import ProjectAirSimClient, World, Drone
from projectairsim.utils import projectairsim_log

from drone.config import SimConfig, SIM_CONFIG

logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """Raised when we cannot reach Project AirSim."""


class DroneClient:
    """
    Wraps ProjectAirSimClient, World, and Drone into one object
    that the rest of the GSCE project talks to.

    Usage:
        with DroneClient() as client:
            prim.takeoff(client)
            prim.move_to_position(client, x=10, y=5, z_agl=8)
    """

    def __init__(self, config: SimConfig = SIM_CONFIG):
        self.config = config
        self.vehicle = config.vehicle_name

        self._client: ProjectAirSimClient | None = None
        self._world: World | None = None
        self._drone: Drone | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # Camera frames stored by subscription callbacks.
        # key: "SensorName/topic_key"  value: latest raw bytes
        self._latest_images: dict[str, bytes] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to Project AirSim and load the scene."""
        logger.info(
            "Connecting to Project AirSim (scene=%s, vehicle=%s)",
            self.config.scene_config,
            self.vehicle,
        )

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            # No args — matches hello_drone.py exactly.
            self._client = ProjectAirSimClient()
            self._client.connect()
        except Exception as exc:
            raise ConnectionError(
                "Could not connect to Project AirSim. "
                "Make sure Unreal Engine is running with the Project AirSim plugin active."
            ) from exc

        try:
            self._world = World(
                self._client,
                self.config.scene_config,
                delay_after_load_sec=self.config.scene_load_delay_s,
            )
            self._drone = Drone(self._client, self._world, self.vehicle)
        except Exception as exc:
            raise ConnectionError(
                f"Connected to Project AirSim but could not load scene "
                f"'{self.config.scene_config}' or find vehicle '{self.vehicle}'. "
                f"Check that the scene config is in your sim_config/ folder "
                f"and that vehicle_name matches the scene config exactly."
            ) from exc

        logger.info("Connected. Scene loaded. Drone '%s' ready.", self.vehicle)

    def enable_api_control(self) -> None:
        """Enable API control and arm the drone."""
        self._require_connected()
        self._drone.enable_api_control()
        self._drone.arm()
        logger.info("API control enabled, drone armed.")

    def disable_api_control(self) -> None:
        """Disarm and release API control."""
        self._require_connected()
        try:
            self._drone.disarm()
            self._drone.disable_api_control()
        except Exception:
            pass
        logger.info("Drone disarmed, API control disabled.")

    def disconnect(self) -> None:
        """Graceful shutdown."""
        if self._client is not None:
            try:
                self.disable_api_control()
            except Exception:
                pass
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
            self._world = None
            self._drone = None
            logger.info("Disconnected from Project AirSim.")

        if self._loop is not None:
            self._loop.close()
            self._loop = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "DroneClient":
        self.connect()
        self.enable_api_control()
        return self

    def __exit__(self, *_) -> None:
        self.disconnect()

    # ------------------------------------------------------------------
    # Async execution helper
    # ------------------------------------------------------------------

    def run_async(self, coro_factory) -> None:
        """
        Run a Project AirSim async command synchronously.

        Project AirSim requires two awaits per command:
            task = await drone.method(...)   # schedule
            await task                       # wait for completion

        Pass a zero-argument lambda that calls the async method:
            client.run_async(lambda: drone.takeoff_async())

        This wrapper handles both awaits so primitives.py stays synchronous.
        """
        self._require_connected()

        async def _run():
            task = await coro_factory()
            await task

        self._loop.run_until_complete(_run())

    # ------------------------------------------------------------------
    # Camera subscription helper
    # ------------------------------------------------------------------

    def subscribe_camera(
        self,
        sensor_name: str,
        image_key: str,
        topic_key: str = "scene_camera",
    ) -> None:
        """
        Subscribe to a camera sensor and store the latest frame.

        Cameras in Project AirSim are pub/sub only. There is no pull API.
        This method sets up a subscription so capture_image() can return
        the most recent frame on demand.

        Args:
            sensor_name: Key into drone.sensors, e.g. "DownCamera" or "Chase".
            image_key: Internal key to store the frame under.
            topic_key: Pub/sub topic key, e.g. "scene_camera" or "depth_camera".
                       These match exactly what the log prints on startup.
        """
        self._require_connected()
        topic = self._drone.sensors[sensor_name][topic_key]

        def _cb(_, data):
            self._latest_images[image_key] = data

        self._client.subscribe(topic, _cb)
        logger.info(
            "Subscribed to drone.sensors['%s']['%s'] as key '%s'",
            sensor_name, topic_key, image_key,
        )

    def get_latest_image(self, image_key: str) -> bytes | None:
        """Return the most recent frame for a subscribed camera, or None."""
        return self._latest_images.get(image_key)

    # ------------------------------------------------------------------
    # Property accessors used by primitives.py
    # ------------------------------------------------------------------

    @property
    def drone(self) -> Drone:
        self._require_connected()
        return self._drone

    @property
    def world(self) -> World:
        self._require_connected()
        return self._world

    @property
    def pa_client(self) -> ProjectAirSimClient:
        self._require_connected()
        return self._client

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_connected(self) -> None:
        if self._client is None:
            raise ConnectionError("Not connected. Call connect() first.")

    def is_connected(self) -> bool:
        return self._client is not None
