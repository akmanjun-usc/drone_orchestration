"""
AirSim connection bridge.

This is the only module that imports airsim directly.
Everything else gets a DroneClient instance from here.
"""

import logging
import time
import airsim

from drone.config import SimConfig, SIM_CONFIG

logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """Raised when we cannot connect to the AirSim sim."""


class DroneClient:
    """
    Thin wrapper around airsim.MultirotorClient.

    Handles connection, arming, and keeps the vehicle name so
    primitives don't have to pass it on every call.
    """

    def __init__(self, config: SimConfig = SIM_CONFIG):
        self.config = config
        self.vehicle = config.vehicle_name
        self._client: airsim.MultirotorClient | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to AirSim and confirm the sim is responding."""
        logger.info(
            "Connecting to AirSim at %s:%d (vehicle=%s)",
            self.config.host,
            self.config.port,
            self.vehicle,
        )

        try:
            self._client = airsim.MultirotorClient(
                ip=self.config.host,
                port=self.config.port,
                timeout_value=self.config.connection_timeout_s,
            )
            self._client.confirmConnection()
        except Exception as exc:
            raise ConnectionError(
                f"Could not connect to AirSim at "
                f"{self.config.host}:{self.config.port} — is Unreal running?"
            ) from exc

        logger.info("Connected to AirSim.")

    def enable_api_control(self) -> None:
        """Enable API control and arm the drone. Must call before any movement."""
        self._require_connected()
        self._client.enableApiControl(True, vehicle_name=self.vehicle)
        self._client.armDisarm(True, vehicle_name=self.vehicle)
        logger.info("API control enabled, drone armed.")

    def disable_api_control(self) -> None:
        """Disarm and release API control."""
        self._require_connected()
        self._client.armDisarm(False, vehicle_name=self.vehicle)
        self._client.enableApiControl(False, vehicle_name=self.vehicle)
        logger.info("API control disabled, drone disarmed.")

    def disconnect(self) -> None:
        """Graceful shutdown — disarm then drop the connection."""
        if self._client is not None:
            try:
                self.disable_api_control()
            except Exception:
                pass  # best-effort on teardown
            self._client = None
            logger.info("Disconnected from AirSim.")

    # ------------------------------------------------------------------
    # Context manager support  (with DroneClient() as client: ...)
    # ------------------------------------------------------------------

    def __enter__(self) -> "DroneClient":
        self.connect()
        self.enable_api_control()
        return self

    def __exit__(self, *_) -> None:
        self.disconnect()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def client(self) -> airsim.MultirotorClient:
        """Raw AirSim client — used only by primitives.py."""
        self._require_connected()
        return self._client

    def _require_connected(self) -> None:
        if self._client is None:
            raise ConnectionError("Not connected. Call connect() first.")

    def is_connected(self) -> bool:
        return self._client is not None
