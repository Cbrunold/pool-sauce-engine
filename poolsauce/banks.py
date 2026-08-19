"""Bank-shot solver (Pillar II, multi-rail) — the D-018 deferral, delivered.

A direct shot can be geometrically impossible (the cut would have to pass
through the ball) yet the ball is still potable off the cushions. This module
finds those paths.

Method
------
1. **Mirror seed.** For a chosen rail sequence, reflect the target pocket
   across those rails (in reverse contact order) to get a virtual pocket.
   The object ball aimed at the virtual pocket travels the unfolded straight
   line — i.e., the real zig-zag bank path.
2. **Forward-sim verification.** Our cushions are not perfect geometric
   mirrors (efficiency 0.75, pace-dependent retention), so the mirror aim is
   only a seed. We simulate the full shot and keep only aims where the target
   ball actually drops in the intended pocket after exactly `num_rails`
   cushion contacts. A small aim×speed search around the seed corrects for the
   cushion's non-ideality.

The simulator is the source of truth: a returned BankPlan has been *verified*
to pot, not merely computed to.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product

import numpy as np

from poolsauce.physics import simulate
from poolsauce.sauce import stroke_to_cue_state
from poolsauce.solver import ShotSolverError, _rotate_2d
from poolsauce.state import Ball, TableState

_RAILS = ("bottom", "top", "left", "right")

# Rails each pocket physically sits on. A cushion graze on one of these as the
# ball enters the pocket is incidental, not a deliberate bank — exclude it from
# the rail count so a corner pot off one rail still reads as a "1-railer".
_POCKET_RAILS: dict[str, set[str]] = {
    "bottom-left": {"bottom", "left"},
    "bottom-right": {"bottom", "right"},
    "top-left": {"top", "left"},
    "top-right": {"top", "right"},
    "side-left": {"left"},
    "side-right": {"right"},
}


@dataclass(frozen=True)
class BankPlan:
    """A verified multi-rail bank-shot plan.

    line_of_aim : unit vector from the cue toward the ghost ball.
    ghost_ball_position : cue center at contact.
    rail_sequence : rails the OBJECT ball strikes, in contact order.
    ob_path_points_m : OB path vertices — start, each rail contact, then pocket.
    cue_speed_m_s : the launch speed that pots (found by search).
    cut_angle_deg : apparent cut at contact.
    """

    target_ball_id: str
    pocket: str
    num_rails: int
    rail_sequence: tuple[str, ...]
    line_of_aim: np.ndarray
    ghost_ball_position: np.ndarray
    ob_path_points_m: tuple[tuple[float, float], ...]
    cue_speed_m_s: float
    cut_angle_deg: float


def _reflect_across_rail(p: np.ndarray, rail: str, table) -> np.ndarray:
    """Reflect a point across a rail's cushion face."""
    x, y = float(p[0]), float(p[1])
    if rail == "bottom":
        return np.array([x, -y])
    if rail == "top":
        return np.array([x, 2.0 * table.length_m - y])
    if rail == "left":
        return np.array([-x, y])
    if rail == "right":
        return np.array([2.0 * table.width_m - x, y])
    raise ValueError(f"unknown rail {rail!r}")


def _rail_sequences(num_rails: int) -> list[tuple[str, ...]]:
    """All rail sequences of the given length with no consecutive repeats."""
    seqs: list[tuple[str, ...]] = []
    for combo in product(_RAILS, repeat=num_rails):
        if all(combo[i] != combo[i + 1] for i in range(len(combo) - 1)):
            seqs.append(combo)
    return seqs


def _trace_bank_path(
    p_ob: np.ndarray,
    ob_dir: np.ndarray,
    sequence: tuple[str, ...],
    table,
    radius_m: float,
) -> list[np.ndarray] | None:
    """Geometric OB bank path: walk the direction, reflecting at each rail's
    ball-center contact line, in the given sequence order. Returns the vertices
    (start + each contact) or None if the path leaves the table out of order.
    """
    lo_x, hi_x = radius_m, table.width_m - radius_m
    lo_y, hi_y = radius_m, table.length_m - radius_m
    pos = p_ob.astype(float).copy()
    d = ob_dir / float(np.linalg.norm(ob_dir))
    pts = [pos.copy()]

    for rail in sequence:
        # Distance to the targeted rail line along d.
        if rail == "bottom":
            if d[1] >= -1e-9:
                return None
            t = (lo_y - pos[1]) / d[1]
        elif rail == "top":
            if d[1] <= 1e-9:
                return None
            t = (hi_y - pos[1]) / d[1]
        elif rail == "left":
            if d[0] >= -1e-9:
                return None
            t = (lo_x - pos[0]) / d[0]
        else:  # right
            if d[0] <= 1e-9:
                return None
            t = (hi_x - pos[0]) / d[0]
        if t <= 1e-6:
            return None
        hit = pos + d * t
        # Must land within the rail's span (not past a corner).
        if not (lo_x - 1e-6 <= hit[0] <= hi_x + 1e-6 and lo_y - 1e-6 <= hit[1] <= hi_y + 1e-6):
            return None
        pts.append(hit.copy())
        # Reflect direction off the rail.
        if rail in ("bottom", "top"):
            d = np.array([d[0], -d[1]])
        else:
            d = np.array([-d[0], d[1]])
        pos = hit
    return pts


def solve_bank_shot(
    state: TableState,
    target_ball_id: str,
    pocket: str,
    num_rails: int,
    cue_ball_id: str = "cue",
    *,
    aim_sweep_deg: float = 8.0,
    aim_steps: int = 13,
    speeds_m_s: tuple[float, ...] = (3.0, 4.2, 5.4, 6.6),
) -> BankPlan:
    """Find a verified bank shot that pots ``target_ball_id`` in ``pocket``
    off exactly ``num_rails`` cushions.

    Raises ``ShotSolverError`` if no potting bank is found.
    """
    if num_rails < 1:
        raise ShotSolverError("num_rails must be >= 1")
    table = state.table
    if pocket not in table.pockets:
        raise ShotSolverError(f"unknown pocket {pocket!r}")

    cue = state.get_ball(cue_ball_id)
    ob = state.get_ball(target_ball_id)
    p_pocket = table.pockets[pocket]
    p_ob = ob.position
    p_cue = cue.position
    r_sum = cue.radius_m + ob.radius_m

    # Sweep aim from the seed outward (0, +1, -1, +2, -2, ...) so the first
    # potting solution found is the closest to the textbook mirror line.
    half = aim_steps // 2
    step_order = [0]
    for k in range(1, half + 1):
        step_order.extend([k, -k])

    for sequence in _rail_sequences(num_rails):
        # Mirror seed: reflect the pocket across the rails in reverse order.
        virtual = p_pocket.astype(float).copy()
        for rail in reversed(sequence):
            virtual = _reflect_across_rail(virtual, rail, table)

        seed_vec = virtual - p_ob
        seed_dist = float(np.linalg.norm(seed_vec))
        if seed_dist < 1e-6:
            continue
        seed_dir = seed_vec / seed_dist

        for k in step_order:
            # Sweep the OB aim direction around the mirror seed.
            frac = k / half if half > 0 else 0.0
            offset = math.radians(aim_sweep_deg) * frac
            ob_dir = _rotate_2d(seed_dir, offset)

            ghost = p_ob - r_sum * ob_dir
            aim_vec = ghost - p_cue
            aim_dist = float(np.linalg.norm(aim_vec))
            if aim_dist < 1e-6:
                continue
            line_of_aim = aim_vec / aim_dist

            cos_cut = float(np.clip(line_of_aim @ ob_dir, -1.0, 1.0))
            if cos_cut <= 1e-3:
                continue  # cut >= ~90°, not achievable
            cut_deg = math.degrees(math.acos(cos_cut))

            path = _trace_bank_path(p_ob, ob_dir, sequence, table, ob.radius_m)
            if path is None:
                continue

            for speed in speeds_m_s:
                cue_state = stroke_to_cue_state(cue, line_of_aim, speed)
                sim_state = TableState(
                    table=table,
                    balls=[cue_state if b.id == cue_ball_id else b for b in state.balls],
                )
                result = simulate(sim_state)

                if target_ball_id not in result.pocketed:
                    continue
                # Confirm the right pocket and exact rail count for the OB.
                ob_cushions = [
                    e for e in result.events
                    if e.kind == "cushion" and target_ball_id in e.ball_ids
                ]
                pocket_evt = next(
                    (e for e in result.events
                     if e.kind == "pocket" and target_ball_id in e.ball_ids),
                    None,
                )
                if pocket_evt is None or pocket_evt.detail != pocket:
                    continue
                # Count deliberate rails only: exclude grazes on the rails the
                # target pocket sits on (incidental to dropping in the pocket).
                pocket_rails = _POCKET_RAILS.get(pocket, set())
                deliberate = [
                    e for e in ob_cushions
                    if e.time < pocket_evt.time and e.detail not in pocket_rails
                ]
                if len(deliberate) != num_rails:
                    continue

                # First verified pot wins — the sweep order makes it the
                # solution closest to the textbook mirror line.
                pocket_xy = (float(p_pocket[0]), float(p_pocket[1]))
                pts = tuple((float(p[0]), float(p[1])) for p in path) + (pocket_xy,)
                return BankPlan(
                    target_ball_id=target_ball_id,
                    pocket=pocket,
                    num_rails=num_rails,
                    rail_sequence=sequence,
                    line_of_aim=line_of_aim,
                    ghost_ball_position=ghost,
                    ob_path_points_m=pts,
                    cue_speed_m_s=speed,
                    cut_angle_deg=cut_deg,
                )

    raise ShotSolverError(
        f"no {num_rails}-rail bank found for {target_ball_id} into {pocket}"
    )
