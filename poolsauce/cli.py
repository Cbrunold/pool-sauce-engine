"""Unit H — the CLI.

A ronin works with less. The CLI loads a table state from JSON, accepts an
intention on the command line, and prints a Pillar I-III plan in Rō's voice.
A second subcommand produces the Pillar V debrief given a prior plan.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from poolsauce.composer import (
    VALID_ACCELERATIONS,
    VALID_FORCES,
    Intention,
    SauceChoice,
    compose_pillar_plan,
)
from poolsauce.debrief import (
    VALID_CORRECT_SIDES,
    VALID_SPIN_VERDICTS,
    DebriefOverrides,
    compose_debrief,
)
from poolsauce.physics import simulate
from poolsauce.sauce import SAUCE_ENGLISH, SAUCE_STROKE, describe_stroke
from poolsauce.solver import solve_cue_destination, solve_direct_shot
from poolsauce.state import POCKET_NAMES, Ball, Table, TableState

PROGRAM_NAME = "poolsauce"


def load_state_from_json(path: Path) -> TableState:
    """Parse a TableState from a JSON file matching the schema's table_state shape."""
    data = json.loads(path.read_text(encoding="utf-8"))

    size = data.get("table_size_m")
    if size is not None:
        table = Table(length_m=float(size[0]), width_m=float(size[1]))
    else:
        table = Table()

    balls: list[Ball] = []
    seen_ids: set[str] = set()
    for entry in data.get("balls", ()):
        ball_id = entry["id"]
        if ball_id in seen_ids:
            raise ValueError(f"duplicate ball id in state JSON: {ball_id!r}")
        seen_ids.add(ball_id)
        balls.append(
            Ball(
                id=ball_id,
                position=np.array([float(entry["x_m"]), float(entry["y_m"])]),
            )
        )

    cue_entry = data.get("cue_ball")
    if cue_entry is not None and "cue" not in seen_ids:
        balls.insert(
            0,
            Ball(
                id="cue",
                position=np.array([float(cue_entry["x_m"]), float(cue_entry["y_m"])]),
            ),
        )

    if not any(b.id == "cue" for b in balls):
        raise ValueError("state JSON must contain a cue ball (id 'cue')")

    return TableState(table=table, balls=balls)


def format_pillar_plan(plan: dict[str, Any]) -> str:
    """Render the plan in Rō's voice, matching the CLAUDE.md output template."""
    p1, p2, p3 = plan["pillar_I"], plan["pillar_II"], plan["pillar_III"]

    dest = p1["destination"]
    dest_line = dest.get("descriptor", "")
    if "coordinates_m" in dest:
        x, y = dest["coordinates_m"]
        dest_line = f"{dest_line} ({x:.2f}, {y:.2f})"

    rails = p2["rails_involved"]
    if rails == ["none"]:
        rails_line = "none"
    elif len(rails) == 1:
        rails_line = f"1 rail: {rails[0]}"
    else:
        rails_line = f"{len(rails)} rails: {' then '.join(rails)}"

    speed = p2["speed_window"]
    if "m_per_s" in speed:
        speed_line = f"{speed['label']} ({speed['m_per_s']:.2f} m/s)"
    else:
        speed_line = speed["label"]

    lines = [
        "— PILLAR I · INTENTION —",
        f"Target:       {p1['target']}",
        f"Pocket:       {p1['pocket']}",
        f"Destination:  {dest_line}",
        "",
        "— PILLAR II · THE PATH —",
        f"Line of aim:     {p2['line_of_aim']['description']}",
        f"Contact point:   {p2['contact_point']['description']}",
        f"Escape route:    {p2['escape_route']['description']}",
        f"Rails involved:  {rails_line}",
        f"Speed window:    {speed_line}",
        "",
        "— PILLAR III · THE SAUCE —",
        f"English:      {p3['english']['sauce_term']}",
        f"Stroke:       {p3['stroke']['sauce_term']}",
        f"Force:        {p3['force']}",
        f"Acceleration: {p3['acceleration']}",
        "",
        f"Recipe: {p3['recipe_rationale']}",
        "",
        "— PILLAR IV · EXECUTION —",
        "(Yours, warrior.)",
    ]
    if "doctrine_line" in plan:
        lines.append("")
        lines.append(f"*{plan['doctrine_line']}*")
    return "\n".join(lines)


def format_debrief(plan: dict[str, Any]) -> str:
    """Format a full plan + Pillar V debrief."""
    p5 = plan.get("pillar_V")
    if p5 is None:
        return format_pillar_plan(plan)

    zl = p5["zone_landing"]
    miss = zl.get("miss_vector_m", [0.0, 0.0])
    risks = ", ".join(p5["risk_zones_crossed"]) or "none"
    mastery = p5["mastery_one_percent"]

    lines = [format_pillar_plan(plan), "", "— PILLAR V · DEBRIEF —"]
    lines.append(f"1. Zone landing:    {zl['zone']} (miss: [{miss[0]:+.3f}, {miss[1]:+.3f}])")
    lines.append(f"2. Correct side:    {p5['correct_side']}")
    notes = p5["spin_review"].get("notes", "")
    sep = " — " if notes else ""
    lines.append(f"3. Spin review:     {p5['spin_review']['verdict']}{sep}{notes}")
    lines.append(f"4. Pace control:    {p5['pace_control']}")
    lines.append(f"5. Risk zones:      {risks}")
    lines.append(f"6. Mastery 1%:      Excellent → {mastery['excellent']}")
    lines.append(f"                    Fragile   → {mastery['fragile']}")
    return "\n".join(lines)


def cmd_plan(args: argparse.Namespace) -> int:
    state = load_state_from_json(Path(args.state))
    dest_xy = tuple(args.dest_xy) if args.dest_xy else None
    intention = Intention(
        target_ball_id=args.target,
        pocket=args.pocket,
        destination_descriptor=args.destination,
        destination_coordinates_m=dest_xy,
        destination_tolerance_m=args.dest_tolerance,
    )

    english = args.english
    stroke = args.stroke
    speed_margin = args.speed_margin

    if args.auto_sauce:
        if dest_xy is None:
            raise SystemExit(
                "--auto-sauce requires --dest-xy to be set (no target to aim for)"
            )
        from poolsauce.solver import solve_direct_shot as _solve_plan_only

        shot_plan = _solve_plan_only(
            state, args.target, args.pocket, cue_ball_id="cue"
        )
        recipe = solve_cue_destination(
            state=state,
            plan=shot_plan,
            target_position=np.array(dest_xy),
        )
        described = describe_stroke(
            vertical_tips=recipe.vertical_tips,
            horizontal_tips=recipe.horizontal_tips,
        )
        english = described.english
        stroke = described.stroke
        speed_margin = recipe.speed_margin

    sauce = SauceChoice(
        english=english,
        stroke=stroke,
        force=args.force,
        acceleration=args.acceleration,
        speed_margin=speed_margin,
    )
    plan = compose_pillar_plan(
        state=state,
        shot_id=args.shot_id,
        intention=intention,
        sauce=sauce,
        doctrine_line=args.doctrine,
    )
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print(format_pillar_plan(plan))
    return 0


def cmd_debrief(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    state = load_state_from_json(Path(args.state))

    target = plan["pillar_I"]["target"]
    pocket = plan["pillar_I"]["pocket"]
    shot_plan = solve_direct_shot(state, target, pocket)

    # Replay the actual stroke from the plan's Sauce, not a default rolling
    # stroke. Speed comes from Pillar II's speed_window; spin comes from
    # Pillar III's english + stroke phrases.
    from poolsauce.sauce import cue_state_from_sauce

    speed_m_s = plan["pillar_II"]["speed_window"].get(
        "m_per_s", shot_plan.min_cue_speed_m_s * args.speed_margin
    )
    english_phrase = plan["pillar_III"]["english"]["sauce_term"]
    stroke_phrase = plan["pillar_III"]["stroke"]["sauce_term"]

    cue = cue_state_from_sauce(
        cue=state.cue_ball,
        direction=shot_plan.line_of_aim,
        speed_m_s=speed_m_s,
        english=english_phrase,
        stroke=stroke_phrase,
    )
    sim_state = TableState(
        table=state.table,
        balls=[cue if b.id == "cue" else b for b in state.balls],
    )
    sim_result = simulate(sim_state)

    overrides = DebriefOverrides(
        spin_verdict=args.spin_verdict,
        correct_side=args.correct_side,
    )
    debriefed = compose_debrief(plan, sim_result, overrides)

    if args.json:
        print(json.dumps(debriefed, indent=2))
    else:
        print(format_debrief(debriefed))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="Rōnin — Pool Sauce shot intelligence CLI.",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    plan = subs.add_parser(
        "plan", help="Compute a Pillar I-III plan from a table state and intention."
    )
    plan.add_argument("--state", required=True, help="Path to table state JSON.")
    plan.add_argument("--target", required=True, help="Object ball ID (e.g. '6').")
    plan.add_argument(
        "--pocket",
        required=True,
        choices=sorted(POCKET_NAMES),
    )
    plan.add_argument(
        "--destination",
        required=True,
        help="Human-readable destination descriptor (where the cue should land).",
    )
    plan.add_argument(
        "--dest-xy",
        nargs=2,
        type=float,
        metavar=("X", "Y"),
        default=None,
        help="Target coordinates in meters; enables richer debrief.",
    )
    plan.add_argument("--dest-tolerance", type=float, default=None)
    plan.add_argument("--shot-id", default="cli-shot")
    plan.add_argument(
        "--english",
        default="none",
        choices=sorted(SAUCE_ENGLISH),
    )
    plan.add_argument(
        "--stroke",
        default="spoon of stun",
        choices=sorted(SAUCE_STROKE),
    )
    plan.add_argument("--force", default="measured dose", choices=VALID_FORCES)
    plan.add_argument(
        "--acceleration", default="controlled", choices=VALID_ACCELERATIONS
    )
    plan.add_argument("--speed-margin", type=float, default=1.15)
    plan.add_argument(
        "--auto-sauce",
        action="store_true",
        help="Let the solver pick english/stroke/speed to land the cue at --dest-xy.",
    )
    plan.add_argument("--doctrine", default=None, help="Optional doctrine line.")
    plan.add_argument("--json", action="store_true", help="Emit raw JSON.")
    plan.set_defaults(func=cmd_plan)

    debrief = subs.add_parser(
        "debrief",
        help="Produce a Pillar V debrief from a prior plan.",
    )
    debrief.add_argument("--plan", required=True, help="Path to the Pillar I-III JSON.")
    debrief.add_argument("--state", required=True, help="Path to the original table state JSON.")
    debrief.add_argument("--speed-margin", type=float, default=1.15)
    debrief.add_argument(
        "--spin-verdict", default="clean", choices=VALID_SPIN_VERDICTS
    )
    debrief.add_argument(
        "--correct-side", default="natural", choices=VALID_CORRECT_SIDES
    )
    debrief.add_argument("--json", action="store_true")
    debrief.set_defaults(func=cmd_debrief)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
