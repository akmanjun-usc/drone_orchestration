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
    main.py                 CLI entry point for everything
    test_bridge.py          Smoke test for AirSim connection
    requirements.txt
    .env.example

    drone/                  Phase 1: AirSim bridge
        config.py           Connection settings and safety limits
        bridge.py           DroneClient, connection lifecycle
        primitives.py       Raw AirSim API calls (only file that imports airsim)

    skills/                 Phase 2: Skill API library
        navigation.py       fly_to, orbit_point, hover, fly_path, return_home
        perception.py       capture_image, get_state, get_altitude, detect_object
        mission.py          survey_grid, search_area, inspect_point
        registry.py         Auto-builds the API doc injected into the prompt

    gsce/                   Phase 3: Prompt builder
        guidelines.py       The G section
        constraints.py      The C section
        examples.py         The E section
        prompt_builder.py   Assembles G + S + C + E into one system prompt

    llm/                    Phase 4: Orchestration engine
        provider.py         Abstract base class, model-agnostic interface
        anthropic_provider  Claude implementation
        openai_provider.py  GPT-4o and Ollama implementation
        factory.py          Picks provider from your .env
        code_extractor.py   Pulls the Python block out of LLM responses
        executor.py         Runs generated code in a sandboxed namespace
        orchestrator.py     Main loop: task in, generate, execute, log

    eval/                   Phase 5: Evaluation harness
        tasks.py            9 tasks across simple, medium, and complex levels
        metrics.py          Scoring functions
        runner.py           Runs tasks and collects results
        compare.py          GSCE vs baseline prompt comparison
        report.py           Prints results table matching paper metrics
```

---

## Dependencies

**System requirements**

- Python 3.11 or higher
- Unreal Engine 5 with the AirSim plugin installed and running
- AirSim configured with at least one multirotor vehicle

**Python packages**

Install everything at once.

```
pip install airsim anthropic openai python-dotenv
```

If airsim fails to install because of a missing msgpackrpc module, install the dependency first.

```
pip install msgpack-rpc-python
pip install airsim
```

**API keys**

You need at least one LLM provider key. Claude is the default.

- Anthropic API key from https://console.anthropic.com
- OpenAI API key from https://platform.openai.com (optional, only if using GPT-4o)

---

## Setup

**Step 1. Clone or extract the project**

```bash
cd your-projects-folder
unzip gsce_drone.zip
cd gsce_drone
```

**Step 2. Create your .env file**

```bash
cp .env.example .env
```

Open .env and fill in your API key and preferred model.

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
```

**Step 3. Start Unreal Engine with AirSim**

Open your Unreal project and press Play. AirSim must be running and listening before you run anything.

**Step 4. Test the connection**

```bash
python test_bridge.py
```

You should see the drone take off, hover for three seconds, and land. If this fails, check the AirSim host and port in drone/config.py before going further.

---

## Running the project

**Single task**

Run one natural language task and exit.

```bash
python main.py task "Fly to x=20, y=10 at 8 metres altitude"
python main.py task "Survey a 50x50 metre area starting at the origin at 15 metres"
python main.py task "Find all objects matching Car_* and inspect the first one"
```

**Interactive REPL**

Type tasks one at a time and watch the drone respond.

```bash
python main.py repl
```

Type `quit` to exit.

**Preview the system prompt**

Print the full assembled GSCE prompt to see what the LLM receives.

```bash
python main.py prompt
```

This is useful when debugging unexpected LLM behaviour. You can see exactly what instructions, skill functions, constraints, and examples the model is working with.

**Run the evaluation**

Compare GSCE against a baseline prompt (Guidelines + Skills only, no Constraints or Examples) across all nine tasks.

```bash
python main.py eval
```

Run specific complexity levels only.

```bash
python main.py eval --complexity simple
python main.py eval --complexity medium
python main.py eval --complexity complex
```

Run each task three times for more reliable numbers.

```bash
python main.py eval --runs 3
```

Results print as a table and save to eval_results.csv.

---

## Switching LLM providers

The orchestrator never calls a vendor SDK directly. All provider code lives in llm/provider.py as an abstract interface. Switching models requires zero changes to any other file.

**Use Claude (default)**

```
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
```

Available Claude models: claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5-20251001

**Use GPT-4o**

```
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
```

**Use a local Ollama model**

Ollama exposes an OpenAI-compatible endpoint, so the openai provider works with it directly. Start Ollama with your model running, then run with a custom base URL.

```bash
python main.py task "Hover at 5 metres" --provider openai --model llama3
```

To set a custom Ollama base URL permanently, edit the openai_provider.py constructor and pass base_url="http://localhost:11434/v1".

**Add a completely new provider**

Create a new file in llm/ that subclasses LLMProvider and implements the complete method. Then register it in llm/factory.py. That is the only change required.

---

## Configuration

**AirSim connection (drone/config.py)**

```python
host: str = "127.0.0.1"    # Change if AirSim is on another machine
port: int = 41451           # Default AirSim port
vehicle_name: str = "Drone1"  # Must match your AirSim settings.json
```

If you run Unreal on a different machine from your Python scripts, set host to that machine's IP address.

The vehicle_name must exactly match the vehicle defined in your AirSim settings.json. Open the file at Documents/AirSim/settings.json and check the Vehicles section.

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

These values are used in two places. The executor enforces them at the Python level. The constraints section of the prompt tells the LLM to respect them when generating code.

```python
max_altitude_m: float = 50.0      # LLM clamps any higher altitude request to this
max_speed_ms: float = 15.0        # LLM clamps any higher speed request to this
min_battery_pct: float = 20.0     # LLM calls return_home if battery drops below this
default_speed_ms: float = 5.0     # Used when the task does not specify a speed
takeoff_altitude_m: float = -3.0  # NED value; negative means up in AirSim
```

If you change these values in config.py, the constraints section of the prompt updates automatically the next time you run. You do not need to edit any prompt text manually.

**Adding or editing constraints (gsce/constraints.py)**

Open the file and edit the list. Each entry is one plain English rule. The LLM reads these and applies them when generating code.

```python
_CONSTRAINTS: list[str] = [
    "Never fly above 50 metres AGL...",
    "Your new rule here.",
]
```

**Adding new skill functions (skills/)**

Add a function to navigation.py, perception.py, or mission.py. Write a clear docstring that includes an Example section. The registry.py file automatically picks it up and adds it to the S section of the prompt. The function is also automatically available in the executor namespace when generated code runs.

**Adding few-shot examples (gsce/examples.py)**

Each example is a tuple of task description and code. Add to the EXAMPLES list. More examples generally improve reliability on similar task types.

---

## Troubleshooting

**Connection refused on test_bridge.py**

Unreal Engine is not running or AirSim has not initialised yet. Press Play in Unreal first, wait for the simulation to start, then run the test.

**Wrong vehicle name error**

The vehicle_name in config.py does not match your settings.json. They must be identical including capitalisation.

**LLM generates code that calls a function that does not exist**

This usually means the guidelines are not strict enough. Open gsce/guidelines.py and make the no-hallucination rule more explicit. You can also add an example in gsce/examples.py that shows the LLM sticking to the defined function list.

**Generated code runs but the drone does not move**

AirSim API control is not enabled. The bridge.py enable_api_control method handles this, but some AirSim versions require you to click a button in the Unreal viewport first. Check the AirSim documentation for your version.

**airsim install fails**

```bash
pip install msgpack-rpc-python
pip install airsim
```

If that still fails, install from the Microsoft AirSim GitHub repo directly.

```bash
pip install git+https://github.com/microsoft/AirSim.git#subdirectory=PythonClient
```

---

## How the orchestration loop works

1. You give the orchestrator a task string.
2. It sends the GSCE system prompt plus your task to the LLM.
3. The LLM returns a Python code block.
4. code_extractor.py pulls the code out of the response.
5. executor.py runs it in a namespace that contains only the skill functions and the drone client.
6. If it raises an exception, the error and traceback go back to the LLM as a follow-up message. It tries to fix the code and resubmit. This happens up to max_retries times.
7. The result is returned as a TaskResult with success flag, token counts, and the generated code.

The LLM never has access to your file system, network, or anything outside the skill namespace. The exec call is scoped to a dict of permitted names.
