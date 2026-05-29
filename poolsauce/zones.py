"""Unit E — Zone evaluator.

Classifies a cue-ball landing as A / B / C relative to the *next shot's
requirements*. A is the natural window — the next shot plays at a small
cut angle, short travel, no blockers. B is an acceptable leave that forces
20-40% more difficulty. C is recovery territory, where the samurai weighs
safety against taking the shot.

Two entry points:

- `classify_zone_for_next_shot(state, next_target, next_pocket)` — runs the
  inverse solver against the hypothetical next shot from the current cue
  position, and grades on cut angle, travel distance, and obstruction.
- `classify_zone_by_distance(actual, target, a_radius, b_radius)` — the
  simpler "did we land where we intended" check for the debrief, purely
  geometric.

Both return a `ZoneClassification` with the single-letter verdict plus a
one-line reason suitable for Pillar V output.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from poolsauce.solver import ShotPlan, ShotSolverError, solve_direct_shot
from poolsauce.state import TableState


# Cut-angle thresholds (degrees).
A_CUT_MAX_DEG: float = 30.0
B_CUT_MAX_DEG: float = 60.0

# Travel-distance threshold for a long-shot penalty (meters). An A-angle
# shot beyond this distance is downgraded to B — the angle is natural,
# but the pace window is tight.
A_TRAVEL_MAX_M: float = 1.5

# Distance-based zones (meters, radius from intended target).
A_RADIUS_M: float = 0.10
B_RADIUS_M: float = 0.30


Zone = Literal["A", "B", "C"]


@dataclass(frozen=True)
class ZoneClassification:
    zone: Zone
    reason: str
    next_shot_plan: ShotPlan | None = None


def classify_zone_for_next_shot(
    state: TableState,
    next_target_ball_id: str,
    next_pocket: str,
    *,
    cue_ball_id: str = "cue",
    a_cut_max_deg: float = A_CUT_MAX_DEG,
    b_cut_max_deg: float = B_CUT_MAX_DEG,
    a_travel_max_m: float = A_TRAVEL_MAX_M,
) -> ZoneClassification:
    """Grade the current cue position as the leave for a specified next shot."""
    try:
        plan = solve_direct_shot(
            state, next_target_ball_id, next_pocket, cue_ball_id=cue_ball_id
        )
    except ShotSolverError as err:
        return ZoneClassification(
            zone="C",
            reason=f"next shot not playable: {err}",
        )

    if plan.blockers:
        return ZoneClassification(
            zone="C",
            reason=f"next shot blocked by {', '.join(plan.blockers)}",
            next_shot_plan=plan,
        )

    cut = plan.cut_angle_deg
    travel = plan.cue_travel_distance_m

    if cut <= a_cut_max_deg:
        base: Zone = "A"
    elif cut <= b_cut_max_deg:
        base = "B"
    else:
        base = "C"

    if base == "A" and travel > a_travel_max_m:
        return ZoneClassification(
            zone="B",
            reason=(
                f"natural angle ({cut:.0f}°) but long travel ({travel:.2f} m) — "
                f"pace window narrows"
            ),
            next_shot_plan=plan,
        )

    reasons = {
        "A": f"natural angle ({cut:.0f}°), short travel ({travel:.2f} m)",
        "B": f"moderate cut ({cut:.0f}°), next shot 20-40% harder",
        "C": f"severe cut ({cut:.0f}°), recovery shot — safety may be correct",
    }
    return ZoneClassification(zone=base, reason=reasons[base], next_shot_plan=plan)


def classify_zone_by_distance(
    actual_position: np.ndarray,
    target_position: np.ndarray,
    a_radius_m: float = A_RADIUS_M,
    b_radius_m: float = B_RADIUS_M,
) -> ZoneClassification:
    """Grade based purely on distance from the intended target zone center."""
    actual = np.asarray(actual_position, dtype=float).reshape(2)
    target = np.asarray(target_position, dtype=float).reshape(2)
    dist = float(np.linalg.norm(actual - target))

    if dist <= a_radius_m:
        return ZoneClassification(
            zone="A", reason=f"landed {dist:.2f} m from target — inside A zone"
        )
    if dist <= b_radius_m:
        return ZoneClassification(
            zone="B", reason=f"landed {dist:.2f} m from target — B zone"
        )
    return ZoneClassification(
        zone="C", reason=f"landed {dist:.2f} m from target — C zone, recovery needed"
    )
