"""Unit G — Pillar V composer (the debrief engine).

Given a shot plan and a simulated (or reported) outcome, produce the
six-point Pillar V review. The honesty engine — brutal clarity without
emotional charge.

The composer auto-computes what the physics knows (zone landing, pace
control, risk zones from the event log) and leaves the subjective verdicts
(spin chemistry, correct side, the 1% excellent/fragile) to caller overrides
with sensible defaults. Rō never invents verdicts it cannot back.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from poolsauce.physics import SimulationResult
from poolsauce.zones import (
    A_RADIUS_M,
    B_RADIUS_M,
    classify_zone_by_distance,
)


VALID_CORRECT_SIDES = ("high", "low", "natural", "forced")
VALID_SPIN_VERDICTS = (
    "clean", "too much", "not enough", "wrong axis", "overcooked", "undercooked",
)
VALID_PACE_CONTROL = (
    "clean", "punchy", "decelerated", "floated", "stunned-late", "stunned-early",
)
VALID_RISK_ZONES = (
    "scratch path",
    "traffic",
    "cluster danger",
    "2-rail scratch route",
    "sharp-angled carom",
    "hooked behind blockers",
)


@dataclass(frozen=True)
class DebriefOverrides:
    """Subjective Pillar V fields that need human judgment.

    Sensible defaults keep the schema valid when the caller has no strong
    opinion; override any field to inject a specific verdict.
    """
    spin_verdict: str = "clean"
    spin_notes: str = ""
    pace_control: str | None = None  # None ⇒ auto-derive from miss magnitude
    correct_side: str = "natural"
    risk_zones_crossed: tuple[str, ...] = ()
    mastery_excellent: str = "The stroke followed the plan."
    mastery_fragile: str = "The next 1% is pace calibration."


def compose_debrief(
    plan: dict[str, Any],
    sim_result: SimulationResult,
    overrides: DebriefOverrides = DebriefOverrides(),
    *,
    cue_ball_id: str = "cue",
    a_radius_m: float = A_RADIUS_M,
    b_radius_m: float = B_RADIUS_M,
) -> dict[str, Any]:
    """Build the Pillar V debrief block for a plan's shot_id.

    Returns a copy of ``plan`` with ``pillar_V`` populated. The zone and
    pace_control fields are auto-derived from the simulated cue landing
    versus the plan's intended destination; every other field comes from
    ``overrides`` (or its defaults).

    Raises
    ------
    KeyError
        The plan has no destination coordinates, or the cue ball is missing
        from the simulation result.
    ValueError
        An override violates the schema enum.
    """
    _validate_overrides(overrides)

    intended = _intended_destination(plan)
    actual = _actual_cue_landing(sim_result, cue_ball_id)
    miss = actual - intended

    zone = classify_zone_by_distance(
        actual_position=actual,
        target_position=intended,
        a_radius_m=a_radius_m,
        b_radius_m=b_radius_m,
    ).zone
    pace = overrides.pace_control or _infer_pace(miss, a_radius_m, b_radius_m)

    pillar_V = {
        "zone_landing": {
            "zone": zone,
            "actual_coordinates_m": [float(actual[0]), float(actual[1])],
            "miss_vector_m": [float(miss[0]), float(miss[1])],
        },
        "correct_side": overrides.correct_side,
        "spin_review": {
            "verdict": overrides.spin_verdict,
            "notes": overrides.spin_notes or _default_spin_notes(overrides.spin_verdict),
        },
        "pace_control": pace,
        "risk_zones_crossed": list(overrides.risk_zones_crossed),
        "mastery_one_percent": {
            "excellent": overrides.mastery_excellent,
            "fragile": overrides.mastery_fragile,
        },
    }

    out = dict(plan)
    out["pillar_V"] = pillar_V
    return out


def _validate_overrides(overrides: DebriefOverrides) -> None:
    if overrides.spin_verdict not in VALID_SPIN_VERDICTS:
        raise ValueError(
            f"spin_verdict must be one of {VALID_SPIN_VERDICTS}, "
            f"got {overrides.spin_verdict!r}"
        )
    if overrides.correct_side not in VALID_CORRECT_SIDES:
        raise ValueError(
            f"correct_side must be one of {VALID_CORRECT_SIDES}, "
            f"got {overrides.correct_side!r}"
        )
    if overrides.pace_control is not None and overrides.pace_control not in VALID_PACE_CONTROL:
        raise ValueError(
            f"pace_control must be one of {VALID_PACE_CONTROL}, "
            f"got {overrides.pace_control!r}"
        )
    for risk in overrides.risk_zones_crossed:
        if risk not in VALID_RISK_ZONES:
            raise ValueError(
                f"risk zone must be one of {VALID_RISK_ZONES}, got {risk!r}"
            )


def _intended_destination(plan: dict[str, Any]) -> np.ndarray:
    dest = plan.get("pillar_I", {}).get("destination", {})
    coords = dest.get("coordinates_m")
    if coords is None:
        raise KeyError(
            "plan has no destination coordinates — debrief requires "
            "Intention.destination_coordinates_m"
        )
    return np.asarray(coords, dtype=float).reshape(2)


def _actual_cue_landing(result: SimulationResult, cue_ball_id: str) -> np.ndarray:
    for ball in result.final_balls:
        if ball.id == cue_ball_id:
            return ball.position
    raise KeyError(f"cue ball {cue_ball_id!r} not found in simulation result")


def _infer_pace(miss: np.ndarray, a_radius_m: float, b_radius_m: float) -> str:
    """Map miss magnitude onto the schema's pace-control vocabulary."""
    mag = float(np.linalg.norm(miss))
    if mag <= a_radius_m:
        return "clean"
    if mag <= b_radius_m:
        return "punchy"  # missed but in the general ballpark
    return "floated"     # drifted well past where it was supposed to land


def _default_spin_notes(verdict: str) -> str:
    """Brand-safe one-liner when the caller does not supply specific notes."""
    templates = {
        "clean":        "Sauce held its line; chemistry matched the recipe.",
        "too much":     "Over-seasoned — the sauce carried the cue past the A zone.",
        "not enough":   "Under-seasoned — the cue arrived flat of the recipe.",
        "wrong axis":   "Spin axis off-plumb; next stroke, square the tip.",
        "overcooked":   "The stroke ran past the stroke window; dial it back.",
        "undercooked":  "The stroke pulled up short of the stroke window.",
    }
    return templates.get(verdict, "Chemistry audit pending.")
