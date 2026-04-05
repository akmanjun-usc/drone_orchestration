# GSCE Drone Orchestration

LLM-driven drone control for AirSim using the GSCE prompt framework. You give the drone a task in plain English. The LLM writes Python code using your defined skill functions. That code runs against a live AirSim simulation in Unreal Engine.

Based on the paper: [GSCE: A Prompt Framework with Enhanced Reasoning for Reliable LLM-driven Drone Control](https://arxiv.org/abs/2502.12531)

---

## What GSCE means

The system prompt sent to the LLM has four sections.

**G Guidelines** tell the LLM its role, what output format to use, and which functions it is allowed to call.

**S Skill APIs** are the Python functions the LLM can call. Every function signature and docstring is injected here automatically from your skills folder.

**C Constraints** are safety rules in plain English. Max altitude, max speed, battery thresholds, return-to-home rules. The LLM reasons about these before choosing parameters.

**E Examples** are five task-to-code pairs that show the LLM how to apply constraints inline, not as an afterthought.

The paper shows that adding C and E to a basic G+S prompt significantly improves task success rates, especially on complex multi-step missions.

---

## Project structure

```
gsce_drone/
    main.py                     CLI entry point for everything
    test_bridge.py              Smoke test for the AirSim connection
    requirements.txt
    .env.example

    drone/                      Phase 1: AirSim bridge
        config.py               Connection settings and safety limits
        bridge.py               DroneClient, connection lifecycle
        primitives.py           Raw AirSim API calls (only file that imports airsim)

    skills/                     Phase 2: Skill API library
        navigation.py           fly_to, orbit_point, hover, fly_path, return_home
        perception.py           capture_image, get_state, get_altitude, detect_object
        mission.py              survey_grid, search_area, inspect_point
        registry.py             Auto-builds the API doc injected into the prompt

    gsce/                       Phase 3: Prompt builder
        guidelines.py           The G section
        constraints.py          The C section
        examples.py             The E section
        prompt_builder.py       Assembles G + S + C + E into one system prompt

    llm/                        Phase 4: Orchestration engine
        provider.py             Abstract base class, model-agnostic interface
        anthropic_provider.py   Claude implementation
        openai_provider.py      GPT-4o and Ollama implementation
        groq_provider.py        Groq implementation (Llama, Mixtral, Gemma)
        factory.py              Picks provider from your .env
        code_extractor.py       Pulls the Python block out of LLM responses
        executor.py             Runs generated code in a sandboxed namespace
        orchestrator.py         Main loop: task in, generate, execute, log

    eval/                       Phase 5: Evaluation harness
        tasks.py                9 tasks across simple, medium, and complex levels
        metrics.py              Scoring functions
        runner.py               Runs tasks and collects results
        compare.py              GSCE vs baseline prompt comparison
        report.py               Prints results table matching paper metrics
```

---

## Simulator compatibility

This project supports both the original AirSim and the newer Project AirSim on UE5.

**Original AirSim** works out of the box with no changes.

**Project AirSim** requires replacing three files in the drone/ folder. All other files are identical. See the Project AirSim section at the bottom of this README.

---

## Dependencies

**System requirements**

- Python 3.11 or higher
- Unreal Engine 5 with the AirSim or Project AirSim plugin installed and running
- At least one multirotor vehicle configured in your sim

**Python packages for original AirSim**

```bash
pip install msgpack-rpc-python
pip install airsim anthropic openai groq python-dotenv
```

Install msgpack-rpc-python first. The airsim package will fail without it. If it still fails, install airsim directly from the source repo.

```bash
pip install git+https://github.com/microsoft/AirSim.git#subdirectory=PythonClient
```

**Python packages for Project AirSim**

```bash
pip install projectairsim anthropic openai groq python-dotenv
```

Note that projectairsim may not be on PyPI depending on your version. Check the Project AirSim client setup docs for the exact install command for your build.

**API keys required**

You need at least one LLM provider key. Claude is the default.

- Anthropic (Claude): https://console.anthropic.com
- OpenAI (GPT-4o): https://platform.openai.com
- Groq (Llama, Mixtral): https://console.groq.com (free tier available)

---

## Setup

**Step 1. Extract the project**

```bash
unzip gsce_drone.zip
cd gsce_drone
```

**Step 2. Install dependencies**

```bash
pip install msgpack-rpc-python
pip install airsim anthropic openai groq python-dotenv
```

**Step 3. Create your .env file**

```bash
cp .env.example .env
```

Open .env and fill in your key and preferred model. The file is pre-filled with Claude as the default.

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
```

**Step 4. Start Unreal Engine with AirSim**

Press Play in your Unreal project. AirSim must be fully initialised before you run anything.

**Step 5. Test the connection**

```bash
python test_bridge.py
```

You should see the drone take off, hover for three seconds, and land. If this fails, check the host and port in drone/config.py before going further.

---

## Running the project

**Single task**

```bash
python main.py task "Fly to x=20, y=10 at 8 metres altitude"
python main.py task "Survey a 50x50 metre area starting at the origin at 15 metres"
python main.py task "Find all objects matching Car_* and inspect the first one"
```

**Interactive REPL**

Type tasks one at a time and watch the drone respond. Type quit to exit.

```bash
python main.py repl
```

**Preview the system prompt**

Print the full assembled GSCE prompt to see exactly what the LLM receives. Useful when debugging unexpected LLM behaviour.

```bash
python main.py prompt
```

**Run the evaluation**

Compare GSCE against a baseline prompt (Guidelines + Skills only, no Constraints or Examples) across all nine tasks.

```bash
python main.py eval
```

Run only a specific complexity level.

```bash
python main.py eval --complexity simple
python main.py eval --complexity medium
python main.py eval --complexity complex
```

Run each task multiple times for more reliable numbers.

```bash
python main.py eval --runs 3
```

Results print as a table and save to eval_results.csv.

---

## LLM providers

The orchestrator never calls a vendor SDK directly. All provider code sits behind an abstract interface in llm/provider.py. Switching models only requires a change to your .env file.

**Claude (default)**

```
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
```

Other Claude models: claude-opus-4-6, claude-haiku-4-5-20251001

**GPT-4o**

```
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
```

Other OpenAI models: gpt-4o-mini

**Groq**

Groq runs open-source models with very low latency. The free tier is rate-limited by tokens per minute. The GSCE system prompt is around 4,000 tokens, so you will hit the cap quickly on the free tier with the 70B model. Use llama-3.1-8b-instant if you need a higher rate limit, though it is less reliable on complex multi-step tasks.

```
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
```

Other Groq models: llama-3.1-8b-instant, mixtral-8x7b-32768, gemma2-9b-it

**Ollama (local models)**

Ollama exposes an OpenAI-compatible API, so the openai provider works with it directly. Start Ollama with your model running, then pass the provider and model on the command line.

```bash
python main.py task "Hover at 5 metres" --provider openai --model llama3
```

To make this permanent, open llm/openai_provider.py and set base_url in the constructor.

```python
base_url="http://localhost:11434/v1"
```

**Adding a new provider**

Create a file in llm/ that subclasses LLMProvider and implements the complete method. Register it in llm/factory.py with an elif block. Nothing else changes.

---

## Configuration

**AirSim connection (drone/config.py)**

```python
host: str = "127.0.0.1"      # Change if AirSim is on a different machine
port: int = 41451             # Default AirSim port
vehicle_name: str = "Drone1"  # Must match your AirSim settings.json exactly
```

The vehicle_name must exactly match the vehicle defined in Documents/AirSim/settings.json.

```json
{
    "Vehicles": {
        "Drone1": {
            "VehicleType": "SimpleFlight"
        }
    }
}
```

**Safety limits (drone/config.py)**

```python
max_altitude_m: float = 50.0      # LLM clamps any higher altitude request to this
max_speed_ms: float = 15.0        # LLM clamps any higher speed request to this
min_battery_pct: float = 20.0     # LLM calls return_home if battery drops below this
default_speed_ms: float = 5.0     # Used when the task does not specify a speed
takeoff_altitude_m: float = -3.0  # NED convention, negative means up
```

Changing these values automatically updates the C section of the GSCE prompt on the next run. You do not need to edit any prompt text manually.

**Adding or editing constraints (gsce/constraints.py)**

Each entry in the list is one plain English safety rule.

```python
_CONSTRAINTS: list[str] = [
    "Never fly above 50 metres AGL...",
    "Your new rule here.",
]
```

**Adding new skill functions (skills/)**

Add a function to navigation.py, perception.py, or mission.py. Write a clear docstring with an Example section. The registry.py file picks it up automatically, adds it to the S section of the prompt, and makes it available in the executor namespace. No other changes needed.

**Adding few-shot examples (gsce/examples.py)**

Each example is a tuple of a task description string and a code string. Add to the EXAMPLES list. More examples improve reliability on similar task types.

---

## Project AirSim on UE5

Project AirSim is the successor to the original AirSim and uses a completely different Python client library. Only three files in the drone/ folder need replacing. Everything else is identical.

**Key API differences**

The original AirSim uses a single airsim.MultirotorClient object. Project AirSim splits this into three objects you create in sequence: ProjectAirSimClient for the network connection, World for loading the scene, and Drone for flight control and sensors.

All movement calls are async (asyncio) rather than blocking with .join(). The new bridge.py handles this internally so no other code changes.

Angles are radians in Project AirSim, not degrees. The new primitives.py converts internally so your skill functions and generated code are unaffected.

Camera names are descriptive strings like "front_center" defined in your robot config JSONC, not numeric strings like "0".

There are two ports instead of one: port_topics for pub/sub sensor data and port_services for command request/response.

**How to apply the patch**

Download the Project AirSim patch zip. Copy its files into your existing gsce_drone folder.

```bash
cp patch/drone/config.py     gsce_drone/drone/config.py
cp patch/drone/bridge.py     gsce_drone/drone/bridge.py
cp patch/drone/primitives.py gsce_drone/drone/primitives.py
cp patch/requirements.txt    gsce_drone/requirements.txt
cp patch/test_bridge.py      gsce_drone/test_bridge.py
```

Reinstall dependencies.

```bash
pip uninstall airsim
pip install projectairsim anthropic openai groq python-dotenv
```

**Project AirSim config (drone/config.py)**

```python
host: str = "127.0.0.1"
port_topics: int = 4760        # pub/sub sensor data
port_services: int = 4761      # command request/response
scene_config: str = "scene_basic_drone.jsonc"
vehicle_name: str = "Drone1"
```

The scene_config must match the filename of your JSONC scene config. Project AirSim does not use settings.json.

---

## Troubleshooting

**Connection refused on test_bridge.py**

Unreal Engine is not running or AirSim has not finished initialising. Press Play in Unreal, wait for the simulation to fully load, then run the test.

**Wrong vehicle name error**

The vehicle_name in config.py does not match your settings.json or scene config JSONC. They must be identical including capitalisation.

**LLM generates a function that does not exist**

The model is hallucinating function names. Strengthen the no-hallucination rule in gsce/guidelines.py. You can also add an example in gsce/examples.py that demonstrates the correct function for a similar task.

**Generated code runs but the drone does not move**

API control is not enabled. The bridge.py enable_api_control method handles this automatically, but some AirSim versions require you to click Allow API Control in the Unreal viewport first.

**Groq rate limit errors**

You are hitting the free tier token-per-minute cap. Switch to llama-3.1-8b-instant which has a higher rate limit, or upgrade to a paid Groq plan.

**airsim install fails**

```bash
pip install msgpack-rpc-python
pip install airsim
```

If that still fails, install from the source repo.

```bash
pip install git+https://github.com/microsoft/AirSim.git#subdirectory=PythonClient
```

---

## How the orchestration loop works

1. You give the orchestrator a task string in plain English.
2. It sends the GSCE system prompt plus your task to the LLM.
3. The LLM returns a Python code block.
4. code_extractor.py pulls the code out of the response.
5. executor.py runs it in a namespace containing only the skill functions and the drone client.
6. If the code raises an exception, the error and traceback go back to the LLM as a follow-up message. It tries to fix the code and resubmit. This repeats up to max_retries times.
7. The result comes back as a TaskResult with a success flag, token counts, and the generated code.

The LLM never has access to your file system, network, or anything outside the skill namespace. The exec call is scoped to a dict of explicitly permitted names.
