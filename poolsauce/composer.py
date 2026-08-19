"""Unit F — Pillar I-III composer.

The front door. Pulls from Units A-E to produce a full Pillar I-III plan
that validates against ``pillars.schema.json``. This is the public function
Rōnin calls when producing a shot plan.

Pillar I (intention): target / pocket / destination, echoed back from caller.
Pillar II (path): line of aim, contact point, escape route, rails, speed —
    derived from the inverse solver and a forward simulation of the planned
    stroke.
Pillar III (sauce): english, stroke, force, acceleration, recipe rationale —
    translated from the caller's Sauce prescription into schema-safe enums.
Pillar IV: a constant acknowledgment; execution belongs to the user.
Pillar V: absent here. Produced by `compose_debrief` in a later unit.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from poolsauce.physics import SimulationResult, simulate
from poolsauce.sauce import (
    SAUCE_ENGLISH,
    SAUCE_STROKE,
    aim_for_cue_path,
    cue_state_from_sauce,
    describe_stroke,
    squirt_angle_rad,
    stroke_to_cue_state,
    tip_offsets_from_phrases,
)
from poolsauce.solver import ShotPlan, solve_direct_shot
from poolsauce.state import TableState


VALID_FORCES = ("soft", "measured dose", "firm", "break")
VALID_ACCELERATIONS = ("decelerating into", "controlled", "accelerating through")


@dataclass(frozen=True)
class Intention:
    """Pillar I input: what the shooter wants to happen."""
    target_ball_id: str
    pocket: str
    destination_descriptor: str
    destination_coordinates_m: tuple[float, float] | None = None
    destination_tolerance_m: float | None = None


@dataclass(frozen=True)
class SauceChoice:
    """Pillar III input: the shooter's Sauce recipe."""
    english: str = "none"
    stroke: str = "spoon of stun"
    force: str = "measured dose"
    acceleration: str = "controlled"
    recipe_rationale: str | None = None
    speed_margin: float = 1.15
    # Manual spin override (raw tip offsets). When set, these take precedence
    # over the english/stroke phrases — the player dialed the spin directly.
    vertical_tips: float | None = None
    horizontal_tips: float | None = None


def compose_pillar_plan(
    state: TableState,
    shot_id: str,
    intention: Intention,
    sauce: SauceChoice = SauceChoice(),
    *,
    cue_ball_id: str = "cue",
    timestamp: str | None = None,
    doctrine_line: str | None = None,
    optimize_for_destination: bool = False,
    cut_offset_deg: float = 0.0,
) -> dict[str, Any]:
    """Build a full Pillar I-III document.

    If ``optimize_for_destination`` is set and the intention carries
    destination coordinates, the Sauce is *derived* by the cue-destination
    solver (the spin/speed that lands the cue on the leave) rather than taken
    from the caller's ``sauce``. The recipe rationale then earns its spin.

    Raises
    ------
    ShotSolverError
        The intention cannot be realized as a direct shot.
    KeyError
        The Sauce prescription references an unknown phrase.
    ValueError
        The force/acceleration is not a schema enum.
    """
    if sauce.force not in VALID_FORCES:
        raise ValueError(f"force must be one of {VALID_FORCES}, got {sauce.force!r}")
    if sauce.acceleration not in VALID_ACCELERATIONS:
        raise ValueError(
            f"acceleration must be one of {VALID_ACCELERATIONS}, got {sauce.acceleration!r}"
        )

    plan = solve_direct_shot(
        state=state,
        target_ball_id=intention.target_ball_id,
        pocket=intention.pocket,
        cue_ball_id=cue_ball_id,
        aim_offset_deg=cut_offset_deg,
    )

    # Position optimization — let the engine recommend the spin/speed that
    # lands the cue on the stated destination, instead of defaulting to stun.
    optimized_note: str | None = None
    if optimize_for_destination and intention.destination_coordinates_m is not None:
        from poolsauce.solver import solve_cue_destination

        target = np.asarray(intention.destination_coordinates_m, dtype=float)
        recipe = solve_cue_destination(state, plan, target, cue_ball_id=cue_ball_id)
        presc = describe_stroke(recipe.vertical_tips, recipe.horizontal_tips)
        sauce = SauceChoice(
            english=presc.english,
            stroke=presc.stroke,
            force=sauce.force,
            acceleration=sauce.acceleration,
            recipe_rationale=None,  # replaced by the derived rationale below
            speed_margin=recipe.speed_margin,
        )
        optimized_note = _position_rationale(presc, recipe.landing_error_m)

    speed = plan.min_cue_speed_m_s * sauce.speed_margin
    cue = state.get_ball(cue_ball_id)

    # Effective tips: manual override (player dialed the spin directly) wins
    # over the english/stroke phrases. Display labels come from the tips.
    manual_spin = (
        sauce.vertical_tips is not None or sauce.horizontal_tips is not None
    )
    if manual_spin:
        vertical_tips = sauce.vertical_tips if sauce.vertical_tips is not None else 0.0
        horizontal_tips = sauce.horizontal_tips if sauce.horizontal_tips is not None else 0.0
        presc = describe_stroke(vertical_tips, horizontal_tips)
        english_label, stroke_label = presc.english, presc.stroke
    else:
        vertical_tips, horizontal_tips = tip_offsets_from_phrases(
            english=sauce.english, stroke=sauce.stroke
        )
        english_label, stroke_label = sauce.english, sauce.stroke

    # Squirt: side english deflects the cue ball off the stick line. To send
    # the ball down the solved line_of_aim, the stick must aim off-line by the
    # squirt angle; the deflected launch then lands the ball back on the line.
    pivot_m = state.table.squirt_pivot_length_m
    stick_aim = aim_for_cue_path(
        plan.line_of_aim, horizontal_tips, cue.radius_m, pivot_m
    )
    stick_aim = stick_aim / float(np.linalg.norm(stick_aim))
    squirt_deg = math.degrees(
        squirt_angle_rad(horizontal_tips, cue.radius_m, pivot_m)
    )

    cue_after_stroke = stroke_to_cue_state(
        cue=cue,
        direction=stick_aim,
        speed_m_s=speed,
        vertical_tips=vertical_tips,
        horizontal_tips=horizontal_tips,
        squirt_pivot_length_m=pivot_m,
    )

    sim_state = TableState(
        table=state.table,
        balls=[
            cue_after_stroke if b.id == cue_ball_id else b
            for b in state.balls
        ],
    )
    sim_result = simulate(sim_state)

    rails = _rails_touched_by(sim_result, cue_ball_id)

    stroke_type = _stroke_type(vertical_tips)

    output: dict[str, Any] = {
        "shot_id": shot_id,
        "pillar_I": _build_pillar_I(intention),
        "pillar_II": _build_pillar_II(
            cue_position=cue.position,
            plan=plan,
            speed_m_s=speed,
            rails=rails,
            cue_final_position=_cue_final_position(sim_result, cue_ball_id),
            stick_aim=stick_aim,
            squirt_deg=squirt_deg,
        ),
        "pillar_III": _build_pillar_III(
            english=english_label,
            horizontal_tips=horizontal_tips,
            stroke=stroke_label,
            vertical_tips=vertical_tips,
            stroke_type=stroke_type,
            force=sauce.force,
            acceleration=sauce.acceleration,
            recipe_rationale=optimized_note or sauce.recipe_rationale or _default_rationale(
                plan=plan, english=english_label, stroke=stroke_label
            ),
        ),
        "pillar_IV": {
            "owned_by_user": True,
            "note": "The stance, the breath, the stillness, the strike.",
        },
        "table_state": _build_table_state(state, intention.target_ball_id, cue_ball_id),
    }

    # Object-ball outcome: did it drop, and where does it actually travel?
    # The OB leaves along the (possibly cheated) target direction; we draw it
    # the pocket distance so cheating walks the endpoint across the jaws.
    ob = state.get_ball(intention.target_ball_id)
    ob_end = ob.position + plan.ob_direction * plan.ob_to_pocket_distance_m
    output["pillar_II"]["cut_offset_deg"] = cut_offset_deg
    output["pillar_II"]["object_ball_potted"] = (
        intention.target_ball_id in sim_result.pocketed
    )
    output["pillar_II"]["object_ball_path_m"] = [
        [float(ob.position[0]), float(ob.position[1])],
        [float(ob_end[0]), float(ob_end[1])],
    ]

    if timestamp is not None:
        output["timestamp"] = timestamp
    if doctrine_line is not None:
        output["doctrine_line"] = doctrine_line

    return output


def compose_bank_plan(
    state: TableState,
    shot_id: str,
    intention: Intention,
    num_rails: int,
    *,
    cue_ball_id: str = "cue",
    doctrine_line: str | None = None,
) -> dict[str, Any]:
    """Build a Pillar I-III plan for a verified multi-rail bank shot.

    Uses the bank solver (mirror seed + forward-sim verification). The plan
    carries the object ball's bank path under ``pillar_II.bank`` so the overlay
    can draw the zig-zag. Raises ``ShotSolverError`` if no bank pots.
    """
    from poolsauce.banks import solve_bank_shot  # local import avoids cycle

    bank = solve_bank_shot(
        state, intention.target_ball_id, intention.pocket, num_rails,
        cue_ball_id=cue_ball_id,
    )

    cue = state.get_ball(cue_ball_id)
    rail_seq = bank.rail_sequence
    contact_fraction = 1.0 - math.sin(math.radians(bank.cut_angle_deg))

    pillar_II: dict[str, Any] = {
        "line_of_aim": {
            "description": (
                f"{num_rails}-rail bank off the {' then '.join(rail_seq)} rail"
                f" — aim the {intention.target_ball_id} at the mirror"
            ),
            "vector": [
                float(cue.position[0]), float(cue.position[1]),
                float(bank.ghost_ball_position[0]),
                float(bank.ghost_ball_position[1]),
            ],
        },
        "contact_point": {
            "description": f"{bank.cut_angle_deg:.0f}° cut to start the bank",
            "cut_angle_deg": bank.cut_angle_deg,
            "ball_fraction": contact_fraction,
        },
        "escape_route": {
            "description": f"object ball banks: {' then '.join(rail_seq)}",
            "path_points_m": [
                [float(bank.ghost_ball_position[0]), float(bank.ghost_ball_position[1])],
            ],
        },
        "rails_involved": list(rail_seq),
        "speed_window": {
            "label": _speed_label(bank.cue_speed_m_s),
            "m_per_s": bank.cue_speed_m_s,
        },
        # Bank-specific: the object ball's zig-zag path for the overlay.
        "bank": {
            "num_rails": num_rails,
            "rail_sequence": list(rail_seq),
            "ob_path_points_m": [list(p) for p in bank.ob_path_points_m],
        },
    }

    output: dict[str, Any] = {
        "shot_id": shot_id,
        "pillar_I": _build_pillar_I(intention),
        "pillar_II": pillar_II,
        "pillar_III": _build_pillar_III(
            english="none",
            horizontal_tips=0.0,
            stroke="spoon of stun",
            vertical_tips=0.0,
            stroke_type="stun",
            force="firm",
            acceleration="accelerating through",
            recipe_rationale=(
                f"firm center-ball to carry the {intention.target_ball_id} "
                f"through {num_rails} rail(s) — banks need pace"
            ),
        ),
        "pillar_IV": {
            "owned_by_user": True,
            "note": "The stance, the breath, the stillness, the strike.",
        },
        "table_state": _build_table_state(state, intention.target_ball_id, cue_ball_id),
    }
    if doctrine_line is not None:
        output["doctrine_line"] = doctrine_line

    return output


def _build_pillar_I(intention: Intention) -> dict[str, Any]:
    destination: dict[str, Any] = {"descriptor": intention.destination_descriptor}
    if intention.destination_coordinates_m is not None:
        destination["coordinates_m"] = list(intention.destination_coordinates_m)
    if intention.destination_tolerance_m is not None:
        destination["tolerance_m"] = intention.destination_tolerance_m
    return {
        "target": intention.target_ball_id,
        "pocket": intention.pocket,
        "destination": destination,
        "intention_pure": True,
    }


def _build_pillar_II(
    cue_position: np.ndarray,
    plan: ShotPlan,
    speed_m_s: float,
    rails: tuple[str, ...],
    cue_final_position: np.ndarray,
    stick_aim: np.ndarray | None = None,
    squirt_deg: float = 0.0,
) -> dict[str, Any]:
    loa: dict[str, Any] = {
        "description": _loa_description(plan),
        "vector": [
            float(cue_position[0]), float(cue_position[1]),
            float(plan.ghost_ball_position[0]),
            float(plan.ghost_ball_position[1]),
        ],
    }
    # Squirt: with side english the stick aims off the ball's path. Expose the
    # stick-aim line and the deflection so the overlay can show both — "aim
    # here, the ball travels there." Only meaningful when |squirt| is non-trivial.
    if stick_aim is not None and abs(squirt_deg) > 1e-6:
        cue_to_ghost = float(np.hypot(
            plan.ghost_ball_position[0] - cue_position[0],
            plan.ghost_ball_position[1] - cue_position[1],
        ))
        loa["squirt_deg"] = squirt_deg
        loa["stick_aim_vector"] = [
            float(cue_position[0]), float(cue_position[1]),
            float(cue_position[0] + stick_aim[0] * cue_to_ghost),
            float(cue_position[1] + stick_aim[1] * cue_to_ghost),
        ]
    return {
        "line_of_aim": loa,
        "contact_point": {
            "description": _contact_description(plan),
            "cut_angle_deg": plan.cut_angle_deg,
            "ball_fraction": plan.contact_fraction,
        },
        "escape_route": {
            "description": _escape_description(plan, rails),
            "path_points_m": [
                [float(plan.ghost_ball_position[0]), float(plan.ghost_ball_position[1])],
                [float(cue_final_position[0]), float(cue_final_position[1])],
            ],
        },
        "rails_involved": list(rails) if rails else ["none"],
        "speed_window": {
            "label": _speed_label(speed_m_s),
            "m_per_s": speed_m_s,
        },
    }


def _build_pillar_III(
    english: str,
    horizontal_tips: float,
    stroke: str,
    vertical_tips: float,
    stroke_type: str,
    force: str,
    acceleration: str,
    recipe_rationale: str,
) -> dict[str, Any]:
    return {
        "english": {
            "sauce_term": english,
            "tips_offset": horizontal_tips,
        },
        "stroke": {
            "type": stroke_type,
            "sauce_term": stroke,
            "tips_offset_vertical": vertical_tips,
        },
        "force": force,
        "acceleration": acceleration,
        "recipe_rationale": recipe_rationale,
    }


def _build_table_state(
    state: TableState, target_ball_id: str, cue_ball_id: str
) -> dict[str, Any]:
    cue = state.get_ball(cue_ball_id)
    return {
        "cue_ball": {
            "x_m": float(cue.position[0]),
            "y_m": float(cue.position[1]),
        },
        "balls": [
            {
                "id": b.id,
                "x_m": float(b.position[0]),
                "y_m": float(b.position[1]),
                "is_target": b.id == target_ball_id,
            }
            for b in state.balls
        ],
        "table_size_m": [state.table.length_m, state.table.width_m],
    }


def _rails_touched_by(result: SimulationResult, cue_ball_id: str) -> tuple[str, ...]:
    rails: list[str] = []
    for event in result.events:
        if event.kind == "cushion" and cue_ball_id in event.ball_ids and event.detail:
            rails.append(event.detail)
    return tuple(rails)


def _cue_final_position(result: SimulationResult, cue_ball_id: str) -> np.ndarray:
    for ball in result.final_balls:
        if ball.id == cue_ball_id:
            return ball.position
    raise KeyError(f"cue ball {cue_ball_id!r} not found in simulation result")


def _stroke_type(vertical_tips: float) -> str:
    """Map vertical tip offset to the schema's stroke-type enum."""
    if vertical_tips == 0.0:
        return "stun"
    if vertical_tips >= 0.75:
        return "follow"
    if vertical_tips >= 0.125:
        return "stun-follow"
    if vertical_tips <= -0.75:
        return "draw"
    if vertical_tips <= -0.125:
        return "stun-draw"
    return "stun"


def _loa_description(plan: ShotPlan) -> str:
    gx, gy = plan.ghost_ball_position
    return (
        f"aim through the cue center toward the ghost ball at "
        f"({gx:.2f}, {gy:.2f})"
    )


def _contact_description(plan: ShotPlan) -> str:
    cut = plan.cut_angle_deg
    frac = plan.contact_fraction
    if cut < 1.0:
        return "full center-ball hit"
    if abs(frac - 0.5) < 0.06:
        return f"half-ball hit at {cut:.0f}°"
    if frac > 0.75:
        return f"thick hit (~{frac:.2f}), {cut:.0f}° cut"
    if frac < 0.25:
        return f"thin cut (~{frac:.2f}), {cut:.0f}°"
    return f"{frac:.2f}-ball hit, {cut:.0f}° cut"


def _escape_description(plan: ShotPlan, rails: tuple[str, ...]) -> str:
    if not rails:
        return "cue tangents off the stun line, no rails crossed"
    if len(rails) == 1:
        return f"off the {rails[0]} rail"
    return f"{len(rails)}-rail path: {' then '.join(rails)}"


def _speed_label(speed_m_s: float) -> str:
    if speed_m_s < 1.0:
        return "slow"
    if speed_m_s < 2.0:
        return "medium"
    if speed_m_s < 3.5:
        return "firm"
    return "break"


def _position_rationale(presc, landing_error_m: float) -> str:
    """Rationale for a destination-optimized recipe — earns its spin."""
    bits: list[str] = []
    if presc.stroke != "spoon of stun":
        bits.append(presc.stroke)
    if presc.english != "none":
        bits.append(presc.english)
    if not bits:
        lead = "center-ball stun"
    else:
        lead = " with ".join(bits)
    if landing_error_m <= 0.10:
        tail = "lands the cue on the leave"
    elif landing_error_m <= 0.30:
        tail = "carries the cue near the leave"
    else:
        tail = "is the closest the cue gets to the leave — the angle is tight"
    return f"{lead} — {tail}"


def _default_rationale(plan: ShotPlan, english: str, stroke: str) -> str:
    cut_phrase = (
        "clean straight hit"
        if plan.cut_angle_deg < 1.0
        else f"{plan.cut_angle_deg:.0f}° cut"
    )
    parts: list[str] = []
    if stroke != "spoon of stun":
        parts.append(stroke)
    if english != "none":
        parts.append(english)
    if not parts:
        return f"center-ball stun for a {cut_phrase} — no spin needed"
    return f"{' and '.join(parts)} carries the cue through the {cut_phrase}"
