"""
Project AirSim connection bridge — multi-drone edition.

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

Multi-drone design:
  - All drones are created as Drone objects at connect() time.
  - Only a subset ("active" drones) are armed and API-controlled.
  - spawn_drone() promotes an idle drone to active status.
  - set_active_drone() switches which drone the `drone` property returns,
    so all existing primitives work without modification.
"""

import asyncio
import logging

from projectairsim import ProjectAirSimClient, World, Drone
from projectairsim.utils import projectairsim_log

from drone.config import SimConfig, SIM_CONFIG, ALL_DRONE_NAMES

logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """Raised when we cannot reach Project AirSim."""


class DroneClient:
    """
    Wraps ProjectAirSimClient, World, and multiple Drone objects into
    one object that the rest of the GSCE project talks to.

    Usage:
        with DroneClient() as client:
            prim.takeoff(client)
            prim.move_to_position(client, x=10, y=5, z_agl=8)

            # Spawn a second drone and fly it
            client.spawn_drone()
            client.set_active_drone("Drone2")
            prim.takeoff(client)
    """

    def __init__(self, config: SimConfig = SIM_CONFIG):
        self.config = config
        self.vehicle = config.vehicle_name

        self._client: ProjectAirSimClient | None = None
        self._world: World | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # Multi-drone state
        self._drones: dict[str, Drone] = {}          # ALL drones (name → Drone)
        self._active_drones: set[str] = set()         # Names of activated drones
        self._current_drone_name: str = config.vehicle_name  # Currently selected

        # Camera frames stored by subscription callbacks.
        # key: "DroneN/SensorName/topic_key"  value: latest raw bytes
        self._latest_images: dict[str, bytes] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to Project AirSim, load the scene, and initialise all drones."""
        logger.info(
            "Connecting to Project AirSim (scene=%s, drones=%d)",
            self.config.scene_config,
            self.config.max_drones,
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
        except Exception as exc:
            raise ConnectionError(
                f"Connected to Project AirSim but could not load scene "
                f"'{self.config.scene_config}'. Check that the scene config "
                f"is in your sim_config/ folder."
            ) from exc

        # Create Drone objects for every actor in the scene config.
        for name in ALL_DRONE_NAMES[:self.config.max_drones]:
            try:
                self._drones[name] = Drone(self._client, self._world, name)
            except Exception as exc:
                logger.warning(
                    "Could not create Drone object for '%s': %s", name, exc
                )

        if not self._drones:
            raise ConnectionError(
                "No drones could be initialised. Check that your scene config "
                "declares actors named Drone1..Drone10."
            )

        # Activate the configured number of initial drones.
        for name in ALL_DRONE_NAMES[:self.config.initial_active_drones]:
            if name in self._drones:
                self._active_drones.add(name)

        self._current_drone_name = self.config.vehicle_name
        logger.info(
            "Connected. Scene loaded. %d/%d drones active: %s",
            len(self._active_drones),
            len(self._drones),
            sorted(self._active_drones),
        )

    def enable_api_control(self) -> None:
        """Enable API control and arm all active drones."""
        self._require_connected()
        for name in sorted(self._active_drones):
            drone = self._drones[name]
            drone.enable_api_control()
            drone.arm()
        logger.info(
            "API control enabled, %d drone(s) armed: %s",
            len(self._active_drones),
            sorted(self._active_drones),
        )

    def disable_api_control(self) -> None:
        """Disarm and release API control on all active drones."""
        self._require_connected()
        for name in sorted(self._active_drones):
            try:
                drone = self._drones[name]
                drone.disarm()
                drone.disable_api_control()
            except Exception:
                pass
        logger.info("All active drones disarmed, API control disabled.")

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
            self._drones.clear()
            self._active_drones.clear()
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
    # Multi-drone management
    # ------------------------------------------------------------------

    def spawn_drone(self, name: str | None = None) -> str:
        """
        Activate a drone from the pre-defined pool.

        Args:
            name: Explicit drone name (e.g. "Drone3"). If None, the
                  lowest-numbered inactive drone is chosen automatically.

        Returns:
            The name of the newly activated drone.

        Raises:
            RuntimeError: If all drones are already active, or the
                          requested name is invalid / already active.
        """
        self._require_connected()

        if len(self._active_drones) >= self.config.max_drones:
            raise RuntimeError(
                f"Cannot spawn more drones — all {self.config.max_drones} "
                f"are already active."
            )

        if name is not None:
            # Explicit name requested
            if name not in self._drones:
                available = sorted(self._drones.keys() - self._active_drones)
                raise RuntimeError(
                    f"'{name}' is not a valid drone name. "
                    f"Available inactive drones: {available}"
                )
            if name in self._active_drones:
                raise RuntimeError(f"'{name}' is already active.")
            chosen = name
        else:
            # Auto-pick the next available drone
            inactive = sorted(self._drones.keys() - self._active_drones)
            if not inactive:
                raise RuntimeError("No inactive drones left to spawn.")
            chosen = inactive[0]

        # Activate: add to set, enable API control, arm
        self._active_drones.add(chosen)
        drone = self._drones[chosen]
        drone.enable_api_control()
        drone.arm()

        logger.info(
            "Spawned drone '%s' (%d/%d active)",
            chosen,
            len(self._active_drones),
            self.config.max_drones,
        )
        return chosen

    def set_active_drone(self, name: str) -> None:
        """
        Switch which drone the `.drone` property returns.

        All primitives and skill functions use `client.drone`, so this
        effectively re-targets every subsequent command to the chosen drone.

        Args:
            name: Name of an already-active drone.

        Raises:
            ValueError: If the drone is not active.
        """
        if name not in self._active_drones:
            raise ValueError(
                f"'{name}' is not active. Active drones: "
                f"{sorted(self._active_drones)}"
            )
        self._current_drone_name = name
        logger.debug("Active drone switched to '%s'", name)

    def get_active_drone_names(self) -> list[str]:
        """Return sorted list of all active drone names."""
        return sorted(self._active_drones)

    @property
    def active_drone_name(self) -> str:
        """The name of the drone that commands currently target."""
        return self._current_drone_name

    def get_drone_by_name(self, name: str) -> Drone:
        """
        Return the Drone object for a specific active drone.

        Raises:
            ValueError: If the drone is not active.
        """
        if name not in self._active_drones:
            raise ValueError(
                f"'{name}' is not active. Active drones: "
                f"{sorted(self._active_drones)}"
            )
        return self._drones[name]

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
        topic = self._drones[self._current_drone_name].sensors[sensor_name][topic_key]

        def _cb(_, data):
            self._latest_images[image_key] = data

        self._client.subscribe(topic, _cb)
        logger.info(
            "Subscribed to %s.sensors['%s']['%s'] as key '%s'",
            self._current_drone_name, sensor_name, topic_key, image_key,
        )

    def get_latest_image(self, image_key: str) -> bytes | None:
        """Return the most recent frame for a subscribed camera, or None."""
        return self._latest_images.get(image_key)

    # ------------------------------------------------------------------
    # Property accessors used by primitives.py
    # ------------------------------------------------------------------

    @property
    def drone(self) -> Drone:
        """Return the currently selected active drone."""
        self._require_connected()
        if self._current_drone_name not in self._active_drones:
            raise ConnectionError(
                f"Current drone '{self._current_drone_name}' is not active."
            )
        return self._drones[self._current_drone_name]

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
