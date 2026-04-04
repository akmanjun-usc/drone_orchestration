"""
Project AirSim connection bridge.

This is the only module that imports projectairsim directly.
Everything else gets a DroneClient instance from here.

Key differences from the original AirSim bridge:
  - Three objects instead of one: ProjectAirSimClient, World, Drone
  - All movement APIs are async (asyncio, not .join())
  - Angles are in radians, not degrees
  - Two ports instead of one (port_topics and port_services)
"""

import asyncio
import logging

from projectairsim import ProjectAirSimClient, World, Drone

from drone.config import SimConfig, SIM_CONFIG

logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """Raised when we cannot connect to the Project AirSim sim."""


class DroneClient:
    """
    Wraps the three Project AirSim objects (client, world, drone) behind
    the same interface the rest of the project expects.

    Usage:
        with DroneClient() as client:
            prim.takeoff(client)
            prim.fly_to(client, x=10, y=5, z_agl=8)
    """

    def __init__(self, config: SimConfig = SIM_CONFIG):
        self.config = config
        self.vehicle = config.vehicle_name

        self._client: ProjectAirSimClient | None = None
        self._world: World | None = None
        self._drone: Drone | None = None

        # Each DroneClient owns one event loop for running async calls
        self._loop: asyncio.AbstractEventLoop | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to Project AirSim, load the scene, and create the drone object."""
        logger.info(
            "Connecting to Project AirSim at %s (topics=%d, services=%d, vehicle=%s)",
            self.config.host,
            self.config.port_topics,
            self.config.port_services,
            self.vehicle,
        )

        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            self._client = ProjectAirSimClient(
                address=self.config.host,
                port_topics=self.config.port_topics,
                port_services=self.config.port_services,
            )
            self._client.connect()

        except Exception as exc:
            raise ConnectionError(
                f"Could not connect to Project AirSim at {self.config.host} "
                f"(topics={self.config.port_topics}, services={self.config.port_services}). "
                f"Is Unreal Engine running with the Project AirSim plugin active?"
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
                f"'{self.config.scene_config}' or find drone '{self.vehicle}'. "
                f"Check your scene config and vehicle name."
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
        logger.info("API control disabled, drone disarmed.")

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
    # Context manager  (with DroneClient() as client: ...)
    # ------------------------------------------------------------------

    def __enter__(self) -> "DroneClient":
        self.connect()
        self.enable_api_control()
        return self

    def __exit__(self, *_) -> None:
        self.disconnect()

    # ------------------------------------------------------------------
    # Async helper used by primitives.py
    # ------------------------------------------------------------------

    def run(self, coro) -> any:
        """
        Run a Project AirSim coroutine synchronously.

        Project AirSim uses async/await. The rest of this project is
        synchronous. This helper bridges the gap so primitives.py can
        call async drone methods with a simple blocking call.

        Args:
            coro: An awaitable returned by a Drone async method.

        Returns:
            Whatever the coroutine returns.
        """
        self._require_connected()
        return self._loop.run_until_complete(coro)

    # ------------------------------------------------------------------
    # Property accessors used by primitives.py
    # ------------------------------------------------------------------

    @property
    def drone(self) -> Drone:
        """The Project AirSim Drone object."""
        self._require_connected()
        return self._drone

    @property
    def world(self) -> World:
        """The Project AirSim World object."""
        self._require_connected()
        return self._world

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_connected(self) -> None:
        if self._client is None:
            raise ConnectionError("Not connected. Call connect() first.")

    def is_connected(self) -> bool:
        return self._client is not None
