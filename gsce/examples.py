"""
GSCE — E: Examples

Five task-to-code pairs that show the LLM:
  1. How to structure generated code
  2. How to apply constraints inline (not as an afterthought)
  3. How to reason step-by-step via comments

Add more examples here to improve performance on specific task types.
"""

# Each example is a (task_description, generated_code) tuple.
# These are formatted into the system prompt by prompt_builder.py.

EXAMPLES: list[tuple[str, str]] = [

    # --- Example 1: Simple point navigation ---
    (
        "Fly to position x=30, y=20 at 10 metres altitude.",
        """\
# Check altitude: 10 m is within the 50 m limit — OK
# Check speed: using default 5 m/s, within 15 m/s limit — OK
# Drone may be landed; take off first if needed
state = get_state(client)
if state["is_landed"]:
    # Take off to task altitude before moving
    takeoff(client, altitude_m=10)

# Fly to the requested position
fly_to(client, x=30, y=20, altitude_m=10)

# Task complete; return home per constraint
return_home(client)
""",
    ),

    # --- Example 2: Altitude clamping (constraint reasoning) ---
    (
        "Climb to 200 metres and take a photo.",
        """\
# Constraint check: 200 m exceeds the 50 m maximum altitude limit.
# Clamping to 50 m as required by constraint 1.
safe_altitude = 50.0

state = get_state(client)
if state["is_landed"]:
    takeoff(client, altitude_m=safe_altitude)
else:
    # Already airborne — fly to clamped altitude
    fly_to(client, x=state["x"], y=state["y"], altitude_m=safe_altitude)

# Capture photo at safe altitude
photo = capture_image(client, save_path="high_photo.png")

# Return home after mission
return_home(client)
""",
    ),

    # --- Example 3: Multi-step with hover ---
    (
        "Fly to x=10, y=10 at 8 metres, hover for 5 seconds, then move to x=10, y=30.",
        """\
state = get_state(client)
if state["is_landed"]:
    takeoff(client, altitude_m=8)

# Leg 1: fly to first waypoint
fly_to(client, x=10, y=10, altitude_m=8)

# Hold position for requested duration
hover(client, duration_s=5)

# Leg 2: fly to second waypoint at same altitude
fly_to(client, x=10, y=30, altitude_m=8)

# End of task; return home
return_home(client)
""",
    ),

    # --- Example 4: Grid survey with constraint check ---
    (
        "Survey a 40 x 40 metre area starting at x=0, y=0 at 15 metres altitude. "
        "Row spacing 10 metres. Save photos to 'mission_photos'.",
        """\
# Altitude 15 m is within limit — OK
# Speed will use default 5 m/s — within limit — OK

state = get_state(client)
if state["is_landed"]:
    takeoff(client, altitude_m=15)

# Run the grid survey
photos = survey_grid(
    client,
    origin_x=0,
    origin_y=0,
    width_m=40,
    height_m=40,
    altitude_m=15,
    row_spacing_m=10,
    capture_photos=True,
    photo_dir="mission_photos",
)
print(f"Survey complete: {len(photos)} photos captured")

# Constraint: return home after full pattern
return_home(client)
""",
    ),

    # --- Example 5: Object inspection with multi-angle capture ---
    (
        "Find all objects matching 'Car_*', fly to the first one, "
        "and inspect it from 4 angles at 6 metres altitude.",
        """\
state = get_state(client)
if state["is_landed"]:
    takeoff(client, altitude_m=6)

# Locate matching objects in the scene
cars = detect_object(client, "Car_*")
if not cars:
    print("No matching objects found.")
    return_home(client)
else:
    target = cars[0]
    print(f"Inspecting: {target['name']} at ({target['x']:.1f}, {target['y']:.1f})")

    # Inspect from 4 angles at 10 m standoff, 6 m altitude
    # Altitude 6 m is above the 1 m minimum — OK
    photos = inspect_point(
        client,
        target_x=target["x"],
        target_y=target["y"],
        standoff_m=10,
        altitude_m=6,
        num_angles=4,
    )
    print(f"Inspection complete: {len(photos)} photos taken")

    # Return home after mission
    return_home(client)
""",
    ),
]


def build_examples_section() -> str:
    """
    Format all examples as numbered task/code pairs for the system prompt.
    """
    lines = ["## Examples\n"]
    for i, (task, code) in enumerate(EXAMPLES, start=1):
        lines.append(f"### Example {i}")
        lines.append(f"Task: {task}\n")
        lines.append("```python")
        lines.append(code.rstrip())
        lines.append("```\n")
    return "\n".join(lines)
