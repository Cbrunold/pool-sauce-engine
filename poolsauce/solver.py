"""Unit C — inverse shot solver (Pillar II in code).

Given an intention — target ball, pocket, cue ball — compute the geometry and
minimum pace required to produce the shot, and find a stroke recipe that
lands the cue at a desired destination.

Two public entry points:

- ``solve_direct_shot`` — computes the Pillar II path (line of aim, ghost
  ball, cut angle, contact fraction, tangent line, min cue speed). Throw
  compensation is on by default; the ghost is pre-shifted to counter
  cut-induced throw per D-022.

- ``solve_cue_destination`` — given a plan and a target cue-ball landing,
  performs a grid search over speed × vertical english × horizontal english
  and returns the recipe that lands the cue closest to the target. Scratches
  are filtered out.

Multi-cushion paths (banks, kicks) remain deferred.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from poolsauce.physics import GRAVITY_M_S2, simulate
from poolsauce.sauce import stroke_to_cue_state
from poolsauce.state import Ball, TableState


class ShotSolverError(ValueError):
    """The stated intention cannot be realized as a direct shot."""


@dataclass(frozen=True)
class ShotPlan:
    """The Pillar II geometric plan for a direct shot.

    Attributes
    ----------
    target_ball_id, pocket : what the shot is aimed at.
    ghost_ball_position : the cue ball's center at the moment of contact,
        i.e., one contact-distance behind the OB along the OB-to-pocket line.
    line_of_aim : unit vector from the cue's current position to the ghost.
    cue_travel_distance_m : straight-line distance the cue must cover to
        reach the ghost ball.
    cut_angle_deg : angle between the cue's velocity and the line of centers
        at contact. Zero for a straight hit; 90° would be a grazing impossible.
    contact_fraction : 1.0 for a full center-ball hit, 0.0 for an edge miss.
        Equals ``1 - sin(cut_angle)``. Half-ball hit ≈ 0.5.
    ob_direction : unit vector the object ball travels along after contact.
    ob_to_pocket_distance_m : straight-line distance from the OB to the pocket.
    natural_tangent_line : unit vector of the cue's post-collision direction
        under pure stun (no spin, no follow, no draw). Zero for a full hit.
    min_cue_speed_m_s : lower bound on the cue's initial speed for the OB to
        reach the pocket. Derived under a rolling-friction-only model, so it
        is approximate; use it as a floor, add a safety margin.
    rails_involved : rail names in the path. Empty tuple for direct shots.
    blockers : IDs of other balls that sit across the aim segment. Non-empty
        means the direct shot is obstructed; caller must consider a bank or
        kick path.
    """

    target_ball_id: str
    pocket: str
    ghost_ball_position: np.ndarray
    line_of_aim: np.ndarray
    cue_travel_distance_m: float
    cut_angle_deg: float
    contact_fraction: float
    ob_direction: np.ndarray
    ob_to_pocket_distance_m: float
    natural_tangent_line: np.ndarray
    min_cue_speed_m_s: float
    throw_angle_deg: float = 0.0
    rails_involved: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


def solve_direct_shot(
    state: TableState,
    target_ball_id: str,
    pocket: str,
    cue_ball_id: str = "cue",
    *,
    compensate_throw: bool = True,
) -> ShotPlan:
    """Compute the direct-shot Pillar II plan.

    Parameters
    ----------
    state, target_ball_id, pocket, cue_ball_id : inputs.
    compensate_throw : if True (default), shift the ghost ball to counter
        cut-induced throw. If False, returns the pure-geometric ghost — useful
        for teaching/diagnostics but not for live play.

    Raises
    ------
    ShotSolverError
        The pocket is unknown, the object ball is already in it, the cue is
        already at the contact point, or the required cut angle is ≥ 90°.
    """
    table = state.table
    pockets = table.pockets
    if pocket not in pockets:
        raise ShotSolverError(f"unknown pocket {pocket!r}; valid: {sorted(pockets)}")

    cue = state.get_ball(cue_ball_id)
    ob = state.get_ball(target_ball_id)

    p_pocket = pockets[pocket]
    p_ob = ob.position
    p_cue = cue.position
    r_sum = cue.radius_m + ob.radius_m

    ob_to_pocket = p_pocket - p_ob
    ob_to_pocket_dist = float(np.linalg.norm(ob_to_pocket))
    if ob_to_pocket_dist < 1e-9:
        raise ShotSolverError(f"object ball is already in {pocket!r}")
    ob_dir = ob_to_pocket / ob_to_pocket_dist

    e_bb = table.ball_ball_restitution
    mu_bb = table.ball_ball_friction

    # Determine which side of the OB-to-pocket line the cue approaches from —
    # this sets the throw direction. Sign fixed across fixed-point iterations.
    t_hat = np.array([-ob_dir[1], ob_dir[0]])
    geom_ghost = p_ob - r_sum * ob_dir
    geom_aim_vec = geom_ghost - p_cue
    geom_aim_mag = float(np.linalg.norm(geom_aim_vec))
    if geom_aim_mag < 1e-9:
        raise ShotSolverError("cue ball is already at the ghost-ball contact point")
    geom_aim = geom_aim_vec / geom_aim_mag
    tangent_component = float(geom_aim @ t_hat)
    if tangent_component > 1e-12:
        throw_sign = 1.0
    elif tangent_component < -1e-12:
        throw_sign = -1.0
    else:
        throw_sign = 0.0

    # Fixed-point: estimate throw from current cut, re-aim, recompute cut.
    # Two passes settles within <0.01° for realistic inputs.
    throw_angle_rad = 0.0
    if compensate_throw and throw_sign != 0.0:
        for _ in range(2):
            trial_dir = _rotate_2d(ob_dir, -throw_sign * throw_angle_rad)
            trial_ghost = p_ob - r_sum * trial_dir
            trial_aim_vec = trial_ghost - p_cue
            trial_mag = float(np.linalg.norm(trial_aim_vec))
            if trial_mag < 1e-9:
                break
            trial_aim = trial_aim_vec / trial_mag
            cos_phys = float(np.clip(trial_aim @ trial_dir, -1.0, 1.0))
            phys_cut = math.acos(cos_phys)
            if phys_cut >= math.pi / 2 - 1e-6:
                break
            throw_angle_rad = _cut_induced_throw_angle_rad(phys_cut, e_bb, mu_bb)

    # Final compensated direction.
    contact_direction = _rotate_2d(ob_dir, -throw_sign * throw_angle_rad)

    p_ghost = p_ob - r_sum * contact_direction
    cue_to_ghost = p_ghost - p_cue
    cue_travel = float(np.linalg.norm(cue_to_ghost))
    if cue_travel < 1e-9:
        raise ShotSolverError("cue ball is already at the ghost-ball contact point")
    line_of_aim = cue_to_ghost / cue_travel

    # Apparent cut angle (between aim and OB-to-pocket line) — what the player sees.
    cos_cut_apparent = float(np.clip(line_of_aim @ ob_dir, -1.0, 1.0))
    cut_angle_rad = math.acos(cos_cut_apparent)
    cut_angle_deg = math.degrees(cut_angle_rad)
    if cut_angle_deg >= 90.0 - 1e-6:
        raise ShotSolverError(
            f"cut angle {cut_angle_deg:.1f}° is not physically achievable"
        )
    contact_fraction = 1.0 - math.sin(cut_angle_rad)

    # Natural tangent — perpendicular to the physical line of centers.
    cos_cut_phys = float(np.clip(line_of_aim @ contact_direction, -1.0, 1.0))
    perp = line_of_aim - cos_cut_phys * contact_direction
    perp_mag = float(np.linalg.norm(perp))
    natural_tangent = perp / perp_mag if perp_mag > 1e-9 else np.zeros(2)

    # Minimum cue speed (see D-017).
    g = GRAVITY_M_S2
    mu_r = table.cloth_rolling_friction
    mu_s = table.cloth_sliding_friction
    ob_distance_coef = (24.0 * mu_r + 25.0 * mu_s) / (98.0 * g * mu_s * mu_r)
    v_ob_needed = math.sqrt(ob_to_pocket_dist / ob_distance_coef)
    v_cue_contact_needed = v_ob_needed / ((1.0 + e_bb) / 2.0 * cos_cut_phys)
    v_cue_init_min = math.sqrt(
        v_cue_contact_needed * v_cue_contact_needed + 2.0 * mu_r * g * cue_travel
    )

    blockers: list[str] = []
    for other in state.balls:
        if other.id in {cue.id, ob.id}:
            continue
        d_perp = _distance_point_to_segment(other.position, p_cue, p_ghost)
        if d_perp < cue.radius_m + other.radius_m:
            blockers.append(other.id)

    return ShotPlan(
        target_ball_id=target_ball_id,
        pocket=pocket,
        ghost_ball_position=p_ghost,
        line_of_aim=line_of_aim,
        cue_travel_distance_m=cue_travel,
        cut_angle_deg=cut_angle_deg,
        contact_fraction=contact_fraction,
        ob_direction=ob_dir,
        ob_to_pocket_distance_m=ob_to_pocket_dist,
        natural_tangent_line=natural_tangent,
        min_cue_speed_m_s=v_cue_init_min,
        throw_angle_deg=math.degrees(throw_angle_rad) * throw_sign,
        rails_involved=(),
        blockers=tuple(blockers),
    )


def _cut_induced_throw_angle_rad(
    cut_angle_rad: float, e_bb: float, mu_bb: float
) -> float:
    """Magnitude of cut-induced throw for a zero-spin cue hitting a resting OB.

    Derived directly from the B.3 impulse model:
    - Sticking regime (small cuts, `tan(θ) ≤ 3.5·μ·(1+e)`):
          v_OB_t / v_OB_n = 2·tan(θ) / (7·(1+e))
      so the throw angle equals the arctangent of that ratio.
    - Sliding regime (larger cuts):
          v_OB_t / v_OB_n = μ
      so the throw asymptotes to atan(μ) — roughly 3.4° for default values.

    The transition is continuous. Speed dependence is not modeled in v0;
    empirical pool data shows throw decreasing at high pace (shorter
    collision contact time means less friction impulse per unit ball
    momentum), which our time-integrated impulse approximation averages
    out. Calibrate when measurements arrive.
    """
    if cut_angle_rad <= 0.0:
        return 0.0
    tan_cut = math.tan(cut_angle_rad)
    tan_threshold = 3.5 * mu_bb * (1.0 + e_bb)
    if tan_cut <= tan_threshold:
        return math.atan(2.0 * tan_cut / (7.0 * (1.0 + e_bb)))
    return math.atan(mu_bb)


def _rotate_2d(v: np.ndarray, angle_rad: float) -> np.ndarray:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]])


@dataclass(frozen=True)
class CueDestinationRecipe:
    """A stroke recipe that lands the cue near a target destination.

    Attributes
    ----------
    speed_m_s, speed_margin : the chosen cue starting speed, absolute and
        as a multiple of the plan's ``min_cue_speed_m_s``.
    vertical_tips, horizontal_tips : the tip offsets that produce this cue
        state. Feed them through ``describe_stroke`` (Unit D) to name them.
    predicted_cue_landing_m : 2D landing position of the cue under this
        recipe, obtained by forward simulation.
    landing_error_m : distance from the landing to the requested target.
    scratched : True if even the closest non-scratch candidate was not a
        valid shot — only possible when ``fail_on_scratch=False``.
    """

    speed_m_s: float
    speed_margin: float
    vertical_tips: float
    horizontal_tips: float
    predicted_cue_landing_m: np.ndarray
    landing_error_m: float
    scratched: bool = False


def solve_cue_destination(
    state: TableState,
    plan: ShotPlan,
    target_position: np.ndarray,
    *,
    cue_ball_id: str = "cue",
    speed_margin_range: tuple[float, float] = (1.05, 2.5),
    vertical_tips_range: tuple[float, float] = (-1.0, 1.0),
    horizontal_tips_range: tuple[float, float] = (-1.0, 1.0),
    n_speed: int = 7,
    n_vertical: int = 5,
    n_horizontal: int = 5,
    spin_cost_weight: float = 1.0,
    speed_cost_weight: float = 0.6,
    comfort_margin: float = 1.3,
    position_band_m: float = 0.06,
) -> CueDestinationRecipe:
    """Find the most *replicable* stroke that lands the cue near
    ``target_position`` while still potting the object ball.

    Runs a forward simulation for every combination in a coarse grid over
    speed × vertical english × horizontal english. Position is the priority
    objective, so selection is two-stage:

    1. Find the best achievable landing error ``E*`` (among potting candidates
       if any pot, else overall).
    2. Among candidates landing within ``position_band_m`` of ``E*``, return
       the one with the lowest *replicability cost*

           spin_cost_weight · (v_tips² + h_tips²)
         + speed_cost_weight · max(0, margin − comfort)²

       — because maximum spin and pace multiply miscues, mistrokes, and stroke
       variance. Spin and speed must earn their keep in position (worth more
       than ``position_band_m``) or they are dropped.

    Cue scratches are always skipped.

    The search space is deliberately small (default 7·5·5 = 175 sims, each
    fast) — a pragmatic fit for v0. Finer grids or local refinement are
    straightforward upgrades when calibration data arrives.

    Parameters
    ----------
    state : the current table. Only ball positions are read; the solver
        constructs a fresh simulation for each grid point.
    plan : the Pillar II plan this recipe strokes. Must be the plan for the
        same ``state`` — the cue ball position, line of aim, and minimum
        pace all come from it.
    target_position : 2D desired resting position of the cue ball, in meters.
    spin_cost_weight, speed_cost_weight, comfort_margin : tune how strongly
        the search favors a repeatable stroke over the last centimeters of
        position. Higher weights → gentler, more conservative recipes.
    """
    target = np.asarray(target_position, dtype=float).reshape(2)
    cue = state.get_ball(cue_ball_id)

    speeds_margin = np.linspace(
        speed_margin_range[0], speed_margin_range[1], n_speed
    )
    verts = np.linspace(
        vertical_tips_range[0], vertical_tips_range[1], n_vertical
    )
    horizs = np.linspace(
        horizontal_tips_range[0], horizontal_tips_range[1], n_horizontal
    )

    # Collect every viable (non-scratch) candidate with its error, whether it
    # pots, and its replicability cost; select in two stages afterward.
    candidates: list[tuple[CueDestinationRecipe, bool, float]] = []
    candidates_tried = 0
    scratches = 0

    for s_margin in speeds_margin:
        speed = float(s_margin) * plan.min_cue_speed_m_s
        for v_tips in verts:
            for h_tips in horizs:
                candidates_tried += 1
                cue_after_stroke = stroke_to_cue_state(
                    cue=cue,
                    direction=plan.line_of_aim,
                    speed_m_s=speed,
                    vertical_tips=float(v_tips),
                    horizontal_tips=float(h_tips),
                )
                sim_state = TableState(
                    table=state.table,
                    balls=[
                        cue_after_stroke if b.id == cue_ball_id else b
                        for b in state.balls
                    ],
                )
                result = simulate(sim_state)

                if cue_ball_id in result.pocketed:
                    scratches += 1
                    continue

                cue_final = next(
                    b for b in result.final_balls if b.id == cue_ball_id
                )
                error = float(np.linalg.norm(cue_final.position - target))

                excess = max(0.0, float(s_margin) - comfort_margin)
                replic_cost = (
                    spin_cost_weight * (float(v_tips) ** 2 + float(h_tips) ** 2)
                    + speed_cost_weight * excess * excess
                )
                recipe = CueDestinationRecipe(
                    speed_m_s=speed,
                    speed_margin=float(s_margin),
                    vertical_tips=float(v_tips),
                    horizontal_tips=float(h_tips),
                    predicted_cue_landing_m=cue_final.position.copy(),
                    landing_error_m=error,
                )
                potted = plan.target_ball_id in result.pocketed
                candidates.append((recipe, potted, replic_cost))

    if not candidates:
        raise ShotSolverError(
            f"every stroke combination scratched "
            f"({scratches}/{candidates_tried} candidates)"
        )

    # Stage 1: position is the priority — prefer pots, find the best landing.
    potting = [c for c in candidates if c[1]]
    pool = potting if potting else candidates
    best_error = min(c[0].landing_error_m for c in pool)

    # Stage 2: among recipes within a hair of the best leave, pick the gentlest.
    contenders = [c for c in pool if c[0].landing_error_m <= best_error + position_band_m]
    return min(contenders, key=lambda c: c[2])[0]


@dataclass(frozen=True)
class RankedRecipe:
    """A cue-destination recipe with a difficulty ranking.

    difficulty : a unitless replicability cost — spin magnitude plus excess
        pace. Lower is more repeatable.
    difficulty_label : "stock" | "comfortable" | "tricky" | "hard".
    rank : 1-based, 1 = most replicable.
    makeable : True if the cue lands within the destination tolerance.
    """

    recipe: CueDestinationRecipe
    difficulty: float
    difficulty_label: str
    rank: int
    makeable: bool


def _difficulty_label(difficulty: float) -> str:
    if difficulty < 0.3:
        return "stock"
    if difficulty < 0.7:
        return "comfortable"
    if difficulty < 1.3:
        return "tricky"
    return "hard"


def solve_cue_destination_options(
    state: TableState,
    plan: ShotPlan,
    target_position: np.ndarray,
    *,
    cue_ball_id: str = "cue",
    tolerance_m: float = 0.18,
    max_options: int = 6,
    speed_margin_range: tuple[float, float] = (1.05, 2.5),
    n_speed: int = 7,
    n_vertical: int = 5,
    n_horizontal: int = 5,
    comfort_margin: float = 1.3,
) -> list[RankedRecipe]:
    """Offer several distinct strokes that land the cue near an exact target,
    ranked by how replicable they are (most repeatable first).

    Like solving for an object ball you can cheat into the pocket: many strokes
    reach the same neighborhood by different spin/path, at different difficulty.
    This simulates the grid, keeps strokes that pot the ball and land within
    ``tolerance_m`` of the target, deduplicates to distinct stroke *styles*
    (draw/stun/follow × left/center/right), and ranks them by difficulty.

    Returns up to ``max_options`` RankedRecipe entries. If nothing lands within
    tolerance, returns the closest reachable strokes flagged ``makeable=False``.
    Raises ``ShotSolverError`` only if every candidate scratches.
    """
    target = np.asarray(target_position, dtype=float).reshape(2)
    cue = state.get_ball(cue_ball_id)

    speeds_margin = np.linspace(speed_margin_range[0], speed_margin_range[1], n_speed)
    verts = np.linspace(-1.0, 1.0, n_vertical)
    horizs = np.linspace(-1.0, 1.0, n_horizontal)

    # style key -> best (lowest-difficulty) candidate for that stroke style
    by_style: dict[tuple[int, int], tuple[CueDestinationRecipe, float, bool]] = {}
    any_candidate = False

    for s_margin in speeds_margin:
        speed = float(s_margin) * plan.min_cue_speed_m_s
        for v_tips in verts:
            for h_tips in horizs:
                cue_after = stroke_to_cue_state(
                    cue=cue, direction=plan.line_of_aim, speed_m_s=speed,
                    vertical_tips=float(v_tips), horizontal_tips=float(h_tips),
                )
                sim_state = TableState(
                    table=state.table,
                    balls=[cue_after if b.id == cue_ball_id else b for b in state.balls],
                )
                result = simulate(sim_state)
                if cue_ball_id in result.pocketed:
                    continue  # scratch
                # A recommended stroke must pot the object ball.
                if plan.target_ball_id not in result.pocketed:
                    continue
                any_candidate = True
                cue_final = next(b for b in result.final_balls if b.id == cue_ball_id)
                error = float(np.linalg.norm(cue_final.position - target))
                excess = max(0.0, float(s_margin) - comfort_margin)
                difficulty = abs(float(v_tips)) + abs(float(h_tips)) + 0.6 * excess
                makeable = error <= tolerance_m

                recipe = CueDestinationRecipe(
                    speed_m_s=speed, speed_margin=float(s_margin),
                    vertical_tips=float(v_tips), horizontal_tips=float(h_tips),
                    predicted_cue_landing_m=cue_final.position.copy(),
                    landing_error_m=error,
                )
                # Stroke style: vertical bucket × horizontal bucket.
                vk = -1 if v_tips <= -0.375 else (1 if v_tips >= 0.375 else 0)
                hk = -1 if h_tips <= -0.375 else (1 if h_tips >= 0.375 else 0)
                key = (vk, hk)
                prev = by_style.get(key)
                # Prefer makeable; then lower difficulty; then lower error.
                cand_rank = (not makeable, difficulty, error)
                if prev is None:
                    by_style[key] = (recipe, difficulty, makeable)
                else:
                    prev_rank = (
                        not prev[2], prev[1], prev[0].landing_error_m
                    )
                    if cand_rank < prev_rank:
                        by_style[key] = (recipe, difficulty, makeable)

    if not any_candidate:
        raise ShotSolverError("no stroke pots the ball without scratching")

    entries = list(by_style.values())
    # Makeable first, then by difficulty.
    entries.sort(key=lambda e: (not e[2], e[1], e[0].landing_error_m))
    entries = entries[:max_options]

    return [
        RankedRecipe(
            recipe=rec,
            difficulty=diff,
            difficulty_label=_difficulty_label(diff),
            rank=i + 1,
            makeable=mk,
        )
        for i, (rec, diff, mk) in enumerate(entries)
    ]


def cue_state_from_recipe(
    cue: Ball, plan: ShotPlan, recipe: CueDestinationRecipe
) -> Ball:
    """Build the cue-ball state that executes ``recipe`` along ``plan``'s aim."""
    return stroke_to_cue_state(
        cue=cue,
        direction=plan.line_of_aim,
        speed_m_s=recipe.speed_m_s,
        vertical_tips=recipe.vertical_tips,
        horizontal_tips=recipe.horizontal_tips,
    )


def cue_state_for_plan(cue: Ball, plan: ShotPlan, speed_m_s: float) -> Ball:
    """Build the cue-ball state that executes ``plan`` at the given speed.

    Produces a ball starting at the cue's current position, moving along
    ``plan.line_of_aim`` at ``speed_m_s``, with pure-rolling spin about the
    correct horizontal axis. No side english, no draw, no follow — a clean
    natural-roll stroke. Spin choices are a Pillar III concern (Sauce
    translator); this helper is the minimum that makes the plan simulable.
    """
    if speed_m_s < 0:
        raise ValueError("speed must be non-negative")
    v = plan.line_of_aim * speed_m_s
    R = cue.radius_m
    # Rolling condition: ω_x = -v_y / R,  ω_y = v_x / R.
    w = np.array([-v[1] / R, v[0] / R, 0.0]) if speed_m_s > 0 else np.zeros(3)
    return Ball(
        id=cue.id,
        position=cue.position.copy(),
        velocity=v,
        angular_velocity=w,
        radius_m=cue.radius_m,
        mass_kg=cue.mass_kg,
    )


def _distance_point_to_segment(
    point: np.ndarray, a: np.ndarray, b: np.ndarray
) -> float:
    """Shortest distance from a 2D point to the segment [a, b]."""
    ab = b - a
    ab_len_sq = float(ab @ ab)
    if ab_len_sq < 1e-18:
        return float(np.linalg.norm(point - a))
    t = float((point - a) @ ab / ab_len_sq)
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    closest = a + t * ab
    return float(np.linalg.norm(point - closest))
