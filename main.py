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
    print("Type a task in plain English, or 'quit' to exit.\n")

    with DroneClient() as client:
        orch = Orchestrator(provider=provider, model=model, drone_client=client)

        while True:
            try:
                task = input("task> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not task:
                continue
            if task.lower() in {"quit", "exit", "q"}:
                break

            result = orch.run_task(task)
            status = "PASS" if result.success else "FAIL"
            print(f"[{status}] {result.attempts} attempt(s) | {result.output_tokens} tokens out\n")


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
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
