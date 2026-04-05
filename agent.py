"""
DroneAgent — the perceive-decide-act loop.

Each call to step() does one full iteration:
  1. Perceive  — read drone state
  2. Decide    — ask the LLM for one next action
  3. Act       — execute that action
  4. Check     — evaluate goal completion

Run agent.run() to loop until done or step limit reached.
"""

import logging
import re
import traceback
from dataclasses import dataclass, field

from drone.bridge import DroneClient
from llm.provider import LLMProvider, CompletionRequest, Message
from llm.executor import _validate_code
from skills.registry import get_skill_functions
from agent.goal import Goal
from agent.memory import AgentMemory
from agent.perception import observe, observe_fleet
from agent.agent_prompt import build_agent_system_prompt, build_agent_user_message

logger = logging.getLogger(__name__)

# Tokens that signal the LLM declared the goal done or gave up
_COMPLETE_SIGNAL = "GOAL_COMPLETE"
_ABORT_PREFIX = "GOAL_ABORT:"


@dataclass
class AgentResult:
    goal: Goal
    steps_taken: int
    success: bool
    abort_reason: str | None = None
    step_log: list[dict] = field(default_factory=list)


class DroneAgent:
    """
    Agentic drone controller.

    One agent controls one primary drone (the currently selected drone
    in DroneClient). For multi-drone missions, instantiate one agent
    per drone, each pointed at a different DroneClient selection.

    Usage:
        goal = Goal(
            description="Fly to x=30, y=20 at 10 metres altitude",
            completion_hint="Arrived at x=30, y=20 within 2 metres",
            target_x=30, target_y=20, target_altitude=10,
            max_steps=15,
        )
        agent = DroneAgent(provider, model, client, goal)
        result = agent.run()
    """

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        client: DroneClient,
        goal: Goal,
        verbose: bool = True,
    ):
        self.provider = provider
        self.model = model
        self.client = client
        self.goal = goal
        self.verbose = verbose

        self._system_prompt = build_agent_system_prompt()
        self._memory = AgentMemory(context_window=5)
        self._skill_namespace = get_skill_functions()
        self._skill_namespace["client"] = client

        # Track which drone we're managing
        self._drone_name = client.active_drone_name

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> AgentResult:
        """
        Run the perceive-decide-act loop until the goal is achieved,
        aborted, or the step limit is hit.
        """
        logger.info(
            "Agent starting: drone=%s goal=%r max_steps=%d",
            self._drone_name,
            self.goal.description,
            self.goal.max_steps,
        )

        step_log = []

        while not self.goal.is_over():
            self.goal.steps_taken += 1
            step_num = self.goal.steps_taken

            if self.verbose:
                print(f"\n[Agent] Step {step_num}/{self.goal.max_steps} "
                      f"| drone={self._drone_name}")

            log_entry = self._step(step_num)
            step_log.append(log_entry)

            # Auto-check nav goal completion
            if not self.goal.completed and log_entry.get("outcome") == "success":
                state = log_entry.get("state", {})
                if state and self.goal.check_nav_completion(state):
                    logger.info("Auto-detected nav goal completion.")
                    self.goal.completed = True

            # Auto-check photo goal completion
            if not self.goal.completed and self.goal.check_photo_completion():
                logger.info("Photo goal completion detected.")
                self.goal.completed = True

        # Report outcome
        if self.goal.completed:
            logger.info("Goal achieved in %d steps.", self.goal.steps_taken)
            if self.verbose:
                print(f"\n[Agent] GOAL ACHIEVED in {self.goal.steps_taken} steps.")
        elif self.goal.abort_reason:
            logger.warning("Goal aborted: %s", self.goal.abort_reason)
            if self.verbose:
                print(f"\n[Agent] ABORTED: {self.goal.abort_reason}")
        else:
            logger.warning("Step limit reached without completing goal.")
            if self.verbose:
                print(f"\n[Agent] Step limit ({self.goal.max_steps}) reached.")

        return AgentResult(
            goal=self.goal,
            steps_taken=self.goal.steps_taken,
            success=self.goal.completed,
            abort_reason=self.goal.abort_reason,
            step_log=step_log,
        )

    # ------------------------------------------------------------------
    # One perceive-decide-act cycle
    # ------------------------------------------------------------------

    def _step(self, step_num: int) -> dict:
        """Run one full perceive-decide-act cycle. Returns a log dict."""

        # 1. Perceive
        try:
            state, state_text = observe(self.client)
        except Exception as exc:
            logger.error("Perception failed: %s", exc)
            state, state_text = {}, f"(Perception error: {exc})"

        fleet_text = None
        if len(self.client.get_active_drone_names()) > 1:
            try:
                fleet_text = observe_fleet(self.client)
            except Exception:
                pass

        if self.verbose:
            print(f"  State: {state_text.splitlines()[0]}")

        # 2. Decide
        user_msg = build_agent_user_message(
            goal_description=self.goal.description,
            completion_hint=self.goal.completion_hint,
            step_num=step_num,
            max_steps=self.goal.max_steps,
            state_text=state_text,
            memory_text=self._memory.format_for_prompt(),
            fleet_text=fleet_text,
        )

        request = CompletionRequest(
            system_prompt=self._system_prompt,
            messages=[Message(role="user", content=user_msg)],
            model=self.model,
            max_tokens=256,
            temperature=0.0,
        )

        try:
            response = self.provider.complete(request)
            action_text = response.content.strip()
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            action_text = f"hover(client, duration_s=1)  # LLM error fallback"

        if self.verbose:
            print(f"  Action: {action_text}")

        # 3. Check for terminal signals before executing
        if action_text == _COMPLETE_SIGNAL:
            self.goal.completed = True
            self._memory.record(step_num, state_text, action_text, "goal_complete", self._drone_name)
            return {"step": step_num, "action": action_text, "outcome": "goal_complete", "state": state}

        if action_text.startswith(_ABORT_PREFIX):
            reason = action_text[len(_ABORT_PREFIX):].strip()
            self.goal.abort_reason = reason
            self._memory.record(step_num, state_text, action_text, f"aborted: {reason}", self._drone_name)
            return {"step": step_num, "action": action_text, "outcome": f"aborted: {reason}", "state": state}

        # 4. Validate — catch hallucinations before exec
        validation_err = _validate_code(action_text)
        if validation_err:
            logger.warning("Validation failed: %s", validation_err)
            outcome = f"error: {validation_err}"
            self._memory.record(step_num, state_text, action_text, outcome, self._drone_name)
            return {"step": step_num, "action": action_text, "outcome": outcome, "state": state}

        # 5. Act — execute the single action in the skill namespace
        outcome = self._execute_action(action_text, state)

        # 6. Track photo count if the action captured an image
        if "capture_image" in action_text and outcome == "success":
            self.goal.photos_taken += 1

        # 7. Record in memory
        self._memory.record(step_num, state_text, action_text, outcome, self._drone_name)

        return {"step": step_num, "action": action_text, "outcome": outcome, "state": state}

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    def _execute_action(self, action_text: str, state: dict) -> str:
        """
        Execute a single skill function call string.

        Returns "success" or "error: <message>".
        """
        namespace = dict(self._skill_namespace)

        # Expose builtins needed for simple inline expressions
        namespace["__builtins__"] = {
            "print": print,
            "len": len, "range": range, "int": int, "float": float,
            "str": str, "list": list, "dict": dict, "bool": bool,
            "True": True, "False": False, "None": None,
            "abs": abs, "max": max, "min": min, "round": round,
        }

        try:
            exec(compile(action_text, "<agent_action>", "exec"), namespace)
            return "success"
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("Action failed: %s\n%s", exc, tb)
            return f"error: {exc}"

    def step_once(self) -> dict:
        """
        Run exactly one perceive-decide-act cycle and return the log entry.

        Used by the interactive agent REPL so the outer loop can pause
        between steps and accept user input.

        Returns a dict with keys: step, action, outcome, state, done.
        The 'done' key is True when the goal is over (complete, aborted,
        or step limit reached).
        """
        if self.goal.is_over():
            return {"step": self.goal.steps_taken, "action": None,
                    "outcome": "already_done", "state": {}, "done": True}

        self.goal.steps_taken += 1
        log = self._step(self.goal.steps_taken)

        # Auto nav completion check
        if not self.goal.completed and log.get("outcome") == "success":
            state = log.get("state", {})
            if state and self.goal.check_nav_completion(state):
                self.goal.completed = True

        # Auto photo completion check
        if not self.goal.completed and self.goal.check_photo_completion():
            self.goal.completed = True

        log["done"] = self.goal.is_over()
        return log

    def redirect(self, new_goal_description: str) -> None:
        """
        Replace the current goal with a new one mid-session.

        Resets step count and clears memory so the agent starts fresh
        toward the new goal. The drone stays wherever it is.

        Args:
            new_goal_description: New goal in plain English.
        """
        old = self.goal.description
        self.goal.description = new_goal_description
        self.goal.completed = False
        self.goal.abort_reason = None
        self.goal.steps_taken = 0
        self.goal.photos_taken = 0
        self._memory.clear()
        logger.info("Goal redirected: %r -> %r", old, new_goal_description)
