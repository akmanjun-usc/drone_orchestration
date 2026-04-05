"""
GSCE Drone Orchestration — CLI entry point.

Usage examples:

  # Run a single task interactively (default Claude provider)
  python main.py task "Fly to x=20, y=10 at 8 metres altitude"

  # Run a single task with a specific provider and model
  python main.py task "Survey a 40x40 area at 15m" --provider openai --model gpt-4o

  # Interactive REPL mode — type tasks, get drone responses
  python main.py repl

  # Run full evaluation (all tasks, GSCE vs baseline)
  python main.py eval

  # Run evaluation, simple tasks only, 3 runs per task
  python main.py eval --complexity simple --runs 3

  # Preview the assembled GSCE system prompt
  python main.py prompt
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GSCE LLM-driven drone orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--provider",
        default=os.getenv("LLM_PROVIDER", "anthropic"),
        choices=["anthropic", "openai"],
        help="LLM provider (default: env LLM_PROVIDER or 'anthropic')",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("LLM_MODEL", ""),
        help="Model string (default: env LLM_MODEL or provider default)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="AirSim host IP (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=41451,
        help="AirSim port (default: 41451)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # -- task --
    task_p = sub.add_parser("task", help="Run a single natural-language task")
    task_p.add_argument("description", help="Task description in plain English")
    task_p.add_argument(
        "--retries", type=int, default=2,
        help="Max self-correction retries on code failure (default: 2)",
    )

    # -- repl --
    sub.add_parser("repl", help="Interactive task REPL")

    # -- eval --
    eval_p = sub.add_parser("eval", help="Run GSCE vs baseline evaluation")
    eval_p.add_argument(
        "--complexity",
        choices=["simple", "medium", "complex", "all"],
        default="all",
        help="Task complexity level to evaluate (default: all)",
    )
    eval_p.add_argument(
        "--runs", type=int, default=1,
        help="Runs per task (default: 1)",
    )
    eval_p.add_argument(
        "--csv", default="eval_results.csv",
        help="Path to save CSV results (default: eval_results.csv)",
    )

    # -- prompt --
    sub.add_parser("prompt", help="Print the assembled GSCE system prompt and exit")
    _add_agent_subparser(sub)

    return parser


def cmd_prompt(_args) -> None:
    from gsce.prompt_builder import build_system_prompt
    prompt = build_system_prompt()
    print(prompt)
    print(f"\n{'='*60}")
    print(f"Characters : {len(prompt):,}")
    print(f"Token est. : ~{len(prompt)//4:,}")


def cmd_task(args) -> None:
    from drone.bridge import DroneClient
    from drone.config import SIM_CONFIG
    from llm.factory import get_provider
    from llm.orchestrator import Orchestrator

    SIM_CONFIG.host = args.host
    SIM_CONFIG.port = args.port

    provider, model = get_provider(provider_name=args.provider, model=args.model)
    logger.info("Provider: %s  |  Model: %s", provider.provider_name, model)

    with DroneClient() as client:
        orch = Orchestrator(
            provider=provider,
            model=model,
            drone_client=client,
            max_retries=args.retries,
        )
        result = orch.run_task(args.description)

    print("\n" + "="*60)
    print(f"Task     : {result.task}")
    print(f"Status   : {'PASS' if result.success else 'FAIL'}")
    if result.fleet_plan:
        print(f"Fleet    : {result.fleet_plan.drone_count} drone(s) — {result.fleet_plan.reasoning}")
    print(f"Attempts : {result.attempts}")
    print(f"Tokens   : {result.input_tokens} in / {result.output_tokens} out")
    print(f"Model    : {result.model}")
    if not result.success and result.execution.error:
        print(f"Error    : {result.execution.error}")
    print("="*60)
    sys.exit(0 if result.success else 1)


def cmd_repl(args) -> None:
    from drone.bridge import DroneClient
    from drone.config import SIM_CONFIG
    from llm.factory import get_provider
    from llm.orchestrator import Orchestrator

    SIM_CONFIG.host = args.host
    SIM_CONFIG.port = args.port

    provider, model = get_provider(provider_name=args.provider, model=args.model)
    logger.info("Provider: %s  |  Model: %s", provider.provider_name, model)
    print(f"\nGSCE Drone REPL  [{provider.provider_name} / {model}]")
    print("Type a task in plain English, or use a command:")
    print("  spawn [name]  — activate a new drone (up to 10)")
    print("  drones        — list active drones")
    print("  select <name> — switch which drone receives commands")
    print("  quit          — exit\n")

    with DroneClient() as client:
        orch = Orchestrator(provider=provider, model=model, drone_client=client)

        while True:
            try:
                active = client.active_drone_name
                task = input(f"[{active}] task> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not task:
                continue
            if task.lower() in {"quit", "exit", "q"}:
                break

            # ---- built-in REPL commands for multi-drone management -----
            parts = task.split(maxsplit=1)
            cmd_word = parts[0].lower()

            if cmd_word == "spawn":
                drone_name = parts[1].strip() if len(parts) > 1 else None
                try:
                    activated = client.spawn_drone(drone_name)
                    total = len(client.get_active_drone_names())
                    max_d = client.config.max_drones
                    print(f"✓ Spawned {activated}  ({total}/{max_d} active)\n")
                except RuntimeError as e:
                    print(f"✗ {e}\n")
                continue

            if cmd_word == "drones":
                names = client.get_active_drone_names()
                current = client.active_drone_name
                max_d = client.config.max_drones
                print(f"Active drones ({len(names)}/{max_d}):")
                for n in names:
                    marker = " ◄" if n == current else ""
                    print(f"  • {n}{marker}")
                print()
                continue

            if cmd_word == "select" and len(parts) > 1:
                name = parts[1].strip()
                try:
                    client.set_active_drone(name)
                    print(f"✓ Now controlling {name}\n")
                except ValueError as e:
                    print(f"✗ {e}\n")
                continue

            # ---- LLM task execution ------------------------------------
            result = orch.run_task(task)
            status = "PASS" if result.success else "FAIL"
            fleet_info = ""
            if result.fleet_plan:
                fleet_info = f" | fleet={result.fleet_plan.drone_count}"
            print(f"[{status}] {result.attempts} attempt(s){fleet_info} | {result.output_tokens} tokens out")
            if result.fleet_plan:
                print(f"  Fleet decision: {result.fleet_plan.reasoning}")
            print()


def cmd_eval(args) -> None:
    from drone.bridge import DroneClient
    from drone.config import SIM_CONFIG
    from llm.factory import get_provider
    from eval.tasks import ALL_TASKS, SIMPLE_TASKS, MEDIUM_TASKS, COMPLEX_TASKS
    from eval.compare import compare
    from eval.report import print_report, save_report_csv

    SIM_CONFIG.host = args.host
    SIM_CONFIG.port = args.port

    complexity_map = {
        "simple": SIMPLE_TASKS,
        "medium": MEDIUM_TASKS,
        "complex": COMPLEX_TASKS,
        "all": ALL_TASKS,
    }
    tasks = complexity_map[args.complexity]

    provider, model = get_provider(provider_name=args.provider, model=args.model)
    logger.info("Provider: %s  |  Model: %s  |  Tasks: %d", provider.provider_name, model, len(tasks))

    with DroneClient() as client:
        gsce_summary, baseline_summary = compare(
            tasks=tasks,
            provider=provider,
            model=model,
            drone_client=client,
            runs_per_task=args.runs,
        )

    print_report(gsce_summary, baseline_summary)
    save_report_csv(gsce_summary, baseline_summary, path=args.csv)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    dispatch = {
        "task": cmd_task,
        "repl": cmd_repl,
        "eval": cmd_eval,
        "prompt": cmd_prompt,
        "agent": cmd_agent,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()


def _add_agent_subparser(sub) -> None:
    """Register the 'agent' subcommand. Called from _build_parser."""
    agent_p = sub.add_parser(
        "agent",
        help="Run an agentic drone that perceives, decides, and acts autonomously",
    )
    agent_p.add_argument("goal", help="Goal description in plain English")
    agent_p.add_argument(
        "--steps", type=int, default=20,
        help="Max perceive-decide-act steps before giving up (default: 20)",
    )
    agent_p.add_argument(
        "--target-x", type=float, default=None,
        help="Target X coordinate for nav goals (enables auto-completion check)",
    )
    agent_p.add_argument(
        "--target-y", type=float, default=None,
        help="Target Y coordinate for nav goals",
    )
    agent_p.add_argument(
        "--target-alt", type=float, default=None,
        help="Target altitude AGL for nav goals",
    )
    agent_p.add_argument(
        "--photos", type=int, default=0,
        help="Number of photos required to complete photo/survey goals (default: 0)",
    )
    agent_p.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-step console output",
    )


def cmd_agent(args) -> None:
    from drone.bridge import DroneClient
    from llm.factory import get_provider
    from agent.goal import Goal
    from agent.agent import DroneAgent

    provider, model = get_provider(provider_name=args.provider, model=args.model)
    logger.info("Provider: %s  |  Model: %s", provider.provider_name, model)

    goal = Goal(
        description=args.goal,
        completion_hint=f"The agent will self-report GOAL_COMPLETE when done.",
        max_steps=args.steps,
        target_x=args.target_x,
        target_y=args.target_y,
        target_altitude=args.target_alt,
        photos_required=args.photos,
    )

    with DroneClient() as client:
        agent = DroneAgent(
            provider=provider,
            model=model,
            client=client,
            goal=goal,
            verbose=not args.quiet,
        )
        result = agent.run()

    print("\n" + "=" * 60)
    print(f"Goal     : {result.goal.description}")
    print(f"Status   : {'SUCCESS' if result.success else 'FAILED'}")
    print(f"Steps    : {result.steps_taken}/{result.goal.max_steps}")
    print(f"Photos   : {result.goal.photos_taken}/{result.goal.photos_required}")
    if result.abort_reason:
        print(f"Abort    : {result.abort_reason}")
    print("=" * 60)

    sys.exit(0 if result.success else 1)
