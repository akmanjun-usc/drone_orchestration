"""
Goal representation for an agentic drone.

A Goal holds what the drone is trying to achieve, how to know
when it's done, and hard limits like max steps and altitude.

The LLM evaluates goal completion by checking whether the
completion_hint conditions are satisfied at each step.
"""

from dataclasses import dataclass, field


@dataclass
class Goal:
    """
    What a drone is trying to accomplish.

    Attributes:
        description:      Plain English description of the goal.
                          This goes into every LLM prompt.
        completion_hint:  A short sentence telling the LLM what
                          "done" looks like, e.g. "Reached x=20, y=10"
                          or "All 4 waypoints photographed".
        max_steps:        Hard limit on perceive-decide-act iterations.
                          Prevents infinite loops.
        target_x:         Optional target X coordinate (for nav goals).
        target_y:         Optional target Y coordinate (for nav goals).
        target_altitude:  Optional target altitude AGL (for nav goals).
        arrival_radius_m: How close to target counts as "arrived" (metres).
        photos_required:  For survey/inspection goals, how many photos
                          the agent must take before declaring success.
    """

    description: str
    completion_hint: str = "The goal is complete when the task is done."
    max_steps: int = 20
    target_x: float | None = None
    target_y: float | None = None
    target_altitude: float | None = None
    arrival_radius_m: float = 2.0
    photos_required: int = 0

    # Runtime tracking — updated by the agent loop, not set by the user
    steps_taken: int = field(default=0, init=False)
    photos_taken: int = field(default=0, init=False)
    completed: bool = field(default=False, init=False)
    abort_reason: str | None = field(default=None, init=False)

    def is_over(self) -> bool:
        """Return True if the goal is done, aborted, or out of steps."""
        return self.completed or self.abort_reason is not None or self.steps_taken >= self.max_steps

    def check_nav_completion(self, state: dict) -> bool:
        """
        Auto-check positional completion for navigation goals.

        If target_x and target_y are set, checks whether the drone
        is within arrival_radius_m of the target. Also checks altitude
        if target_altitude is set.

        Returns True if the position condition is satisfied.
        """
        if self.target_x is None or self.target_y is None:
            return False

        dx = state["x"] - self.target_x
        dy = state["y"] - self.target_y
        dist = (dx**2 + dy**2) ** 0.5

        if dist > self.arrival_radius_m:
            return False

        if self.target_altitude is not None:
            dz = abs(state["z_agl"] - self.target_altitude)
            if dz > self.arrival_radius_m:
                return False

        return True

    def check_photo_completion(self) -> bool:
        """Return True if enough photos have been taken."""
        if self.photos_required == 0:
            return False
        return self.photos_taken >= self.photos_required

    def summary(self) -> str:
        """One-line status string for logging."""
        status = "DONE" if self.completed else ("ABORTED" if self.abort_reason else "RUNNING")
        return (
            f"[{status}] step={self.steps_taken}/{self.max_steps} "
            f"photos={self.photos_taken}/{self.photos_required} "
            f"goal={self.description!r}"
        )
