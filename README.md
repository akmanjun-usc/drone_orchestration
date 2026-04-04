# Project AirSim patch — what changed and how to apply it

This folder contains three replacement files for the `drone/` package.
Everything else in the project is identical.

## Files in this patch

```
drone/
    config.py       New port fields, removed single-port setting
    bridge.py       Full rewrite for ProjectAirSimClient + World + Drone
    primitives.py   Full rewrite using Project AirSim async API
requirements.txt    Swap airsim for projectairsim
test_bridge.py      Updated smoke test (camera_name changed to string)
```

## How to apply

Copy these five files into your existing `gsce_drone` folder, overwriting
the originals. Everything else stays the same.

```
cp drone/config.py      ../gsce_drone/drone/config.py
cp drone/bridge.py      ../gsce_drone/drone/bridge.py
cp drone/primitives.py  ../gsce_drone/drone/primitives.py
cp requirements.txt     ../gsce_drone/requirements.txt
cp test_bridge.py       ../gsce_drone/test_bridge.py
```

Then reinstall dependencies.

```
pip uninstall airsim
pip install projectairsim anthropic openai python-dotenv
```

## What actually changed

### config.py

The original had a single `port: int = 41451`. Project AirSim uses two
separate ports. Replace that with:

    port_topics: int = 4760       # pub/sub data
    port_services: int = 4761     # request/response commands

Also added `scene_config` field. Project AirSim loads a JSONC scene file
on startup instead of reading a settings.json file from Documents/AirSim.
Set this to match your scene config filename.

### bridge.py

The original wrapped a single `airsim.MultirotorClient`. Project AirSim
splits this into three objects you must create in order.

    ProjectAirSimClient   handles the network connection
    World                 loads and manages the scene
    Drone                 controls the vehicle and reads sensors

The `DroneClient` wrapper still exposes the same interface to the rest
of the project. The `client.run(coro)` method bridges Project AirSim's
async API to the synchronous code in primitives.py.

### primitives.py

Every function keeps the same name and signature. Internally everything
changed.

Movement calls like `move_to_position_async` are awaited via `client.run()`.
Angles in Project AirSim are radians, not degrees. The `rotate_to_yaw`
function converts degrees to radians internally, so the skills layer does
not need to change.

Camera names changed from numeric strings like "0" to descriptive names
like "front_center" that match your robot config JSONC. Update
`drone/config.py` or pass the name explicitly if yours differs.

The `get_state` function now computes roll/pitch/yaw from a quaternion
using a built-in conversion function rather than calling an airsim utility.

`return_to_home` no longer calls `goHomeAsync` because Project AirSim does
not have that method. It flies to (0, 0) at current altitude and lands.
If you need GPS-based home return, subscribe to the GPS topic in bridge.py
and store the home coordinates on connect.

## Your scene config JSONC

Project AirSim does not use Documents/AirSim/settings.json. You define
your drone in a JSONC file and pass its filename when creating the World
object. The default in config.py is "scene_basic_drone.jsonc".

A minimal drone config looks like this.

```jsonc
{
    "scene-name": "BasicDroneScene",
    "robots": [
        {
            "robot-name": "Drone1",
            "robot-type": "Multirotor",
            "controller": {
                "type": "simple-flight-api"
            },
            "sensors": [
                {
                    "sensor-name": "front_center",
                    "sensor-type": "Camera",
                    "capture-settings": [
                        {
                            "image-type": 0,
                            "capture-enabled": true,
                            "compress": true,
                            "pixels-as-float": false
                        }
                    ],
                    "streaming-enabled": true
                }
            ]
        }
    ]
}
```

The camera name "front_center" must match what you pass to `capture_image`.
The robot name "Drone1" must match `vehicle_name` in config.py.

## What did not change

Skills, GSCE prompt builder, LLM providers, orchestrator, evaluator, main.py.
None of those files know anything about which simulator is running.
