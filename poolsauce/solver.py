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
) -> CueDestinationRecipe:
    """Find a stroke recipe that lands the cue near ``target_position``.

    Runs a forward simulation for every combination in a coarse grid over
    speed × vertical english × horizontal english, and returns the recipe
    whose final cue landing minimizes distance to the target. Scratched
    candidates are skipped unless every candidate scratches, in which case
    the raised ``ShotSolverError`` names the failure.

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

    best: CueDestinationRecipe | None = None
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
                if best is None or error < best.landing_error_m:
                    best = CueDestinationRecipe(
                        speed_m_s=speed,
                        speed_margin=float(s_margin),
                        vertical_tips=float(v_tips),
                        horizontal_tips=float(h_tips),
                        predicted_cue_landing_m=cue_final.position.copy(),
                        landing_error_m=error,
                    )

    if best is None:
        raise ShotSolverError(
            f"every stroke combination scratched "
            f"({scratches}/{candidates_tried} candidates)"
        )

    return best


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
