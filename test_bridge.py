"""
Project AirSim Phase 1 smoke test.

Run this with Unreal Engine + Project AirSim plugin active:
    python test_bridge.py

Expected output:
    Connected. Scene loaded. Drone 'Drone1' ready.
    API control enabled, drone armed.
    Taking off to 3.0 m AGL
    Hover reached at 3.0 m AGL
    State: x=0.00  y=0.00  z_agl=3.00  yaw=0.0°  landed=False
    Hovering for 3.0 s
    Landing...
    Landed.
    API control disabled, drone disarmed.
    Disconnected from Project AirSim.
    PASS
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

from drone.bridge import DroneClient, ConnectionError
from drone import primitives as prim


def run_smoke_test() -> bool:
    try:
        with DroneClient() as client:
            prim.takeoff(client, altitude_m=3.0)

            state = prim.get_state(client)
            print(
                f"State:  x={state['x']:.2f}  y={state['y']:.2f}  "
                f"z_agl={state['z_agl']:.2f}  yaw={state['yaw']:.1f}  "
                f"landed={state['is_landed']}"
            )
            assert state["z_agl"] > 1.0, "Drone did not gain altitude"
            assert not state["is_landed"], "Drone reports landed after takeoff"

            prim.hover(client, duration_s=3.0)
            prim.land(client)

            landed_state = prim.get_state(client)
            assert landed_state["is_landed"], "Drone did not land cleanly"

        print("\nPASS")
        return True

    except ConnectionError as exc:
        print(f"\nCONNECTION ERROR: {exc}")
        print("Make sure Unreal Engine is running with the Project AirSim plugin active.")
        return False

    except AssertionError as exc:
        print(f"\nFAIL: {exc}")
        return False

    except Exception as exc:
        print(f"\nUNEXPECTED ERROR: {exc}")
        raise


if __name__ == "__main__":
    ok = run_smoke_test()
    sys.exit(0 if ok else 1)
