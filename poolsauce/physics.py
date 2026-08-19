"""Shot interaction layer — Units B.1 (free flight), B.2 (cushion rebound),
B.3 (ball-ball collision with throw), and B.4 (event loop).

Free flight: a single ball evolving on cloth under sliding and rolling
friction, with spin decaying independently about the vertical axis.

Cushion rebound: an instantaneous impulse applied when a ball's center crosses
the cushion contact line. Marlow-lite: pace-dependent tangential retention,
side-english coupling into tangential velocity, horizontal spin preserved
through the bounce (its post-rebound effect lives in free flight on the cloth).

Ball-ball collision: an instantaneous pair of impulses along the line of
centers and in the in-plane tangent direction, derived from the coefficient
of restitution and a Coulomb friction law at the contact patch. Cut-induced
and spin-induced throw both fall out of the same tangential impulse — the
former from translational tangential slip, the latter from the tangential
surface velocity that side english (ωz) creates at the contact point.

Conventions (see DECISIONS D-011):
- SI units throughout.
- Position and velocity are 2D, in the table plane.
- Angular velocity is 3D. Horizontal components (ωx, ωy) couple to the
  rolling/sliding dynamics via the no-slip constraint; the vertical component
  (ωz) decays via spinning friction only.

All functions are pure — the input Ball is never mutated. This keeps D-002
open: the forward integrator is a reusable oracle for the future inverse
solver.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from poolsauce.state import Ball, Table, TableState

GRAVITY_M_S2: float = 9.81

# Numerical tolerances. Above slip epsilon = still sliding; below = rolling.
_SLIP_EPS: float = 1e-6
_V_EPS: float = 1e-6
_WZ_EPS: float = 1e-6
_TIME_EPS: float = 1e-12


def contact_slip(
    velocity: np.ndarray,
    angular_velocity: np.ndarray,
    radius_m: float,
) -> np.ndarray:
    """Tangential velocity of the ball's contact point relative to the cloth.

    Derived from u = v + ω × r_c with r_c = (0, 0, -R):
        u_x = v_x - R · ω_y
        u_y = v_y + R · ω_x

    ωz does not appear — point contact makes vertical spin tangentially idle.
    Returns a 2D vector. Zero magnitude ⇔ pure rolling.
    """
    wx, wy, _ = angular_velocity
    return np.array(
        [velocity[0] - radius_m * wy, velocity[1] + radius_m * wx],
        dtype=float,
    )


def is_rolling(ball: Ball, tol: float = _SLIP_EPS) -> bool:
    slip = contact_slip(ball.velocity, ball.angular_velocity, ball.radius_m)
    return float(np.linalg.norm(slip)) <= tol


def step_free_flight(ball: Ball, dt: float, table: Table) -> Ball:
    """Advance the ball by exactly `dt`, through any phase transitions.

    The sliding and rolling phases are integrated analytically — within a
    phase the motion is closed-form, so phase transitions are resolved
    exactly at the epoch they occur.

    Phase ladder within the step:
      1. Sliding. Slip vector decays along its own direction at rate
         (7 μ_s g / 2). Linear velocity decelerates at μ_s g along slip.
         Horizontal angular velocity evolves to enforce the no-slip
         constraint at the transition.
      2. Rolling. Velocity decelerates at μ_r g along its direction.
         Horizontal spin tracks velocity via the rolling constraint.
      3. Stopped. All motion zero.

    Vertical spin decays independently at rate (5 μ_sp g / 2R) over the
    full `dt`, regardless of which horizontal phase the ball is in.
    """
    if dt < 0:
        raise ValueError("dt must be non-negative")

    pos = ball.position.copy()
    vel = ball.velocity.copy()
    w = ball.angular_velocity.copy()

    if dt == 0:
        return _clone(ball, pos, vel, w)

    R = ball.radius_m
    mu_s = table.cloth_sliding_friction
    mu_r = table.cloth_rolling_friction
    mu_sp = table.cloth_spinning_friction
    g = GRAVITY_M_S2

    remaining = float(dt)
    while remaining > _TIME_EPS:
        slip = contact_slip(vel, w, R)
        slip_mag = float(np.linalg.norm(slip))

        if slip_mag > _SLIP_EPS:
            # Sliding. Slip decays at (7/2) μ_s g; velocity decays at μ_s g.
            t_to_roll = slip_mag / (3.5 * mu_s * g)
            t = min(remaining, t_to_roll)
            u_hat = slip / slip_mag

            pos += vel * t - 0.5 * mu_s * g * u_hat * (t * t)
            vel -= mu_s * g * u_hat * t
            # Torque from contact friction: dω/dt = (5 μ_s g / 2R) · (-û_y, û_x, 0).
            w[0] -= 2.5 * mu_s * g / R * u_hat[1] * t
            w[1] += 2.5 * mu_s * g / R * u_hat[0] * t
            remaining -= t

            if t >= t_to_roll:
                # Snap slip to zero and enforce rolling constraint exactly —
                # analytic guarantees; this defends against float drift.
                w[0] = -vel[1] / R
                w[1] = vel[0] / R
            continue

        v_mag = float(np.linalg.norm(vel))
        if v_mag > _V_EPS:
            # Rolling. Uniform deceleration along velocity direction.
            t_to_stop = v_mag / (mu_r * g)
            t = min(remaining, t_to_stop)
            v_hat = vel / v_mag

            pos += vel * t - 0.5 * mu_r * g * v_hat * (t * t)
            vel -= mu_r * g * v_hat * t
            w[0] = -vel[1] / R
            w[1] = vel[0] / R
            remaining -= t

            if t >= t_to_stop:
                vel[:] = 0.0
                w[0] = 0.0
                w[1] = 0.0
            continue

        # Horizontal motion exhausted.
        vel[:] = 0.0
        w[0] = 0.0
        w[1] = 0.0
        break

    # Vertical spin — decoupled from horizontal phases.
    if abs(w[2]) > _WZ_EPS:
        alpha_sp = 2.5 * mu_sp * g / R
        t_spin_stop = abs(w[2]) / alpha_sp
        t = min(float(dt), t_spin_stop)
        w[2] -= alpha_sp * np.sign(w[2]) * t
        if abs(w[2]) < _WZ_EPS:
            w[2] = 0.0
    else:
        w[2] = 0.0

    return _clone(ball, pos, vel, w)


def advance_to_rest(ball: Ball, table: Table, max_time: float = 60.0) -> Ball:
    """Evolve free flight until the ball is fully at rest.

    Since every phase is analytic, one sufficiently long step resolves every
    transition. `max_time` is a safety clamp for pathological inputs.
    """
    return step_free_flight(ball, max_time, table)


# Outward rail normals, in the table plane.
# "Outward" = from the rail into the playing surface, i.e., the direction in
# which a rebound velocity should end up pointing.
RAIL_OUTWARD_NORMALS: dict[str, np.ndarray] = {
    "bottom": np.array([0.0, 1.0]),
    "top": np.array([0.0, -1.0]),
    "left": np.array([1.0, 0.0]),
    "right": np.array([-1.0, 0.0]),
}


def cushion_rebound(ball: Ball, rail: str | np.ndarray, table: Table) -> Ball:
    """Apply an instantaneous cushion impulse to a ball in contact with a rail.

    Marlow-lite model:

    - Normal velocity reflects, scaled by `cushion_efficiency` (energy loss).
    - Tangential velocity is retained with a pace-dependent factor:
          k_t(pace) = max(k_min, k_base - α · pace)
      where pace = |v_n_in|. High-pace banks shorten, low-pace widen.
    - Side english (ω_z) couples into tangential velocity:
          Δv_t = c_spin · R · ω_z
      Running english widens, reverse english shortens.
      ω_z loses magnitude by `side_english_loss` on the bounce.
    - Spin about horizontal axes (ωx, ωy) is preserved in world frame.
      Its effect on the post-rebound path is carried by free-flight cloth
      physics — the brief's "vertical spin affects path, not angle."

    `rail` is either a rail name from `RAIL_OUTWARD_NORMALS` or a 2D unit
    vector specifying the outward normal directly (for arbitrary orientations,
    e.g., a diamond pocket slate or a non-standard angle).

    If the ball is already moving away from the rail (v_n ≥ 0), returns a
    copy with no impulse — the caller is responsible for detecting contact.
    """
    n2d = _resolve_rail_normal(rail)
    t2d = np.array([-n2d[1], n2d[0]])  # 90° CCW from n

    v_in = ball.velocity
    w_in = ball.angular_velocity

    v_n = float(v_in @ n2d)
    v_t = float(v_in @ t2d)

    if v_n >= 0.0:
        return _clone(ball, ball.position.copy(), v_in.copy(), w_in.copy())

    pace = -v_n
    R = ball.radius_m
    e_n = table.cushion_efficiency
    k_t = max(
        table.cushion_tangential_retention_min,
        table.cushion_tangential_retention - table.cushion_tangential_pace_falloff * pace,
    )
    c_spin = table.cushion_side_english_coupling
    spin_loss = table.cushion_side_english_loss
    wz_in = float(w_in[2])

    v_n_out = -e_n * v_n
    v_t_out = k_t * v_t + c_spin * R * wz_in
    v_out = v_n_out * n2d + v_t_out * t2d

    w_out = w_in.copy()
    w_out[2] = wz_in * (1.0 - spin_loss)

    return _clone(ball, ball.position.copy(), v_out, w_out)


def ball_collision(a: Ball, b: Ball, table: Table) -> tuple[Ball, Ball]:
    """Resolve an instantaneous ball-to-ball collision.

    The model:

    - **Normal impulse** along the line of centers, magnitude
      `m_red · (1 + e_bb) · u_n` where `u_n = (v_a − v_b) · n̂` is the
      approach speed and `m_red = m_a·m_b / (m_a + m_b)`. Elastic,
      coefficient-of-restitution `e_bb`. Applied only if approaching.

    - **Tangential (friction) impulse** along the in-plane tangent `t̂`,
      opposing the tangential component of contact-point slip
          u_t = (v_a − v_b) · t̂  +  R_a · ω_{a,z}  +  R_b · ω_{b,z}.
      Magnitude is `min(μ · |J_n|, m_eff_t · |u_t|)` — Coulomb sliding,
      capped by the sticking impulse that would arrest the slip. For equal
      uniform spheres `m_eff_t = m/7`.

    Cut-induced throw comes from the translational `(v_a − v_b) · t̂`
    contribution; spin-induced throw comes from the `R · ω_z` contribution.
    Both act through the same tangential impulse. Horizontal spin components
    (ωx, ωy) contribute only to the out-of-plane slip, which the cloth
    absorbs — consistent with the planar motion assumption (D-011).

    Angular impulse: the tangential impulse, applied at the contact point
    on the side of each ball, produces a z-axis torque on each. This is how
    spin partially transfers from the cue to the object ball — in the
    *opposite* sense to the cue's spin, which matches the documented
    behavior in the pool teaching community.

    If the balls are separating (u_n ≤ 0), both balls are returned unchanged.
    """
    r = b.position - a.position
    dist = float(np.linalg.norm(r))
    if dist <= 0.0:
        raise ValueError("balls share a position; collision geometry is undefined")

    n2d = r / dist
    t2d = np.array([-n2d[1], n2d[0]])

    dv_2d = a.velocity - b.velocity
    u_n = float(dv_2d @ n2d)

    if u_n <= 0.0:
        return (
            _clone(a, a.position.copy(), a.velocity.copy(), a.angular_velocity.copy()),
            _clone(b, b.position.copy(), b.velocity.copy(), b.angular_velocity.copy()),
        )

    m_a, m_b = a.mass_kg, b.mass_kg
    R_a, R_b = a.radius_m, b.radius_m
    I_a = 0.4 * m_a * R_a * R_a
    I_b = 0.4 * m_b * R_b * R_b
    e_bb = table.ball_ball_restitution
    mu_bb = table.ball_ball_friction

    m_red = m_a * m_b / (m_a + m_b)
    J_n_mag = m_red * (1.0 + e_bb) * u_n

    u_t = float(dv_2d @ t2d) + R_a * float(a.angular_velocity[2]) + R_b * float(b.angular_velocity[2])

    if abs(u_t) > 1e-12:
        m_eff_t = 1.0 / (1.0 / m_a + 1.0 / m_b + R_a * R_a / I_a + R_b * R_b / I_b)
        J_t_sticking = m_eff_t * abs(u_t)
        J_t_sliding = mu_bb * J_n_mag
        J_t_scalar = math.copysign(min(J_t_sticking, J_t_sliding), u_t)
    else:
        J_t_scalar = 0.0

    # Linear impulses on B (positive along n̂ and t̂); on A the opposite.
    impulse_B_2d = J_n_mag * n2d + J_t_scalar * t2d
    new_v_a = a.velocity - impulse_B_2d / m_a
    new_v_b = b.velocity + impulse_B_2d / m_b

    # Angular impulse: n̂ × t̂ = +ẑ, so the tangential impulse produces a pure
    # z-torque on each ball. Normal impulse acts through the center — zero torque.
    new_w_a = a.angular_velocity.copy()
    new_w_b = b.angular_velocity.copy()
    new_w_a[2] -= R_a * J_t_scalar / I_a
    new_w_b[2] -= R_b * J_t_scalar / I_b

    return (
        _clone(a, a.position.copy(), new_v_a, new_w_a),
        _clone(b, b.position.copy(), new_v_b, new_w_b),
    )


def _resolve_rail_normal(rail: str | np.ndarray) -> np.ndarray:
    if isinstance(rail, str):
        try:
            return RAIL_OUTWARD_NORMALS[rail]
        except KeyError:
            valid = sorted(RAIL_OUTWARD_NORMALS)
            raise ValueError(f"unknown rail {rail!r}; expected one of {valid}") from None

    arr = np.asarray(rail, dtype=float).reshape(-1)
    if arr.shape != (2,):
        raise ValueError(f"rail normal must be a 2D vector, got shape {arr.shape}")
    mag = float(np.linalg.norm(arr))
    if not math.isclose(mag, 1.0, abs_tol=1e-9):
        raise ValueError(f"rail normal must be a unit vector, got magnitude {mag}")
    return arr


def _clone(template: Ball, pos: np.ndarray, vel: np.ndarray, w: np.ndarray) -> Ball:
    return Ball(
        id=template.id,
        position=pos,
        velocity=vel,
        angular_velocity=w,
        radius_m=template.radius_m,
        mass_kg=template.mass_kg,
    )


# ------------------------------------------------------------------------- #
# Unit B.4 — event loop                                                     #
# ------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SimEvent:
    """A discrete interaction recorded during simulation.

    `time` is absolute, measured from the start of the simulation.
    `kind` is the event type:
      - "cushion": `ball_ids` has one entry, `detail` is the rail name.
      - "collision": `ball_ids` has two entries, `detail` is None.
      - "pocket": `ball_ids` has one entry, `detail` is the pocket name.
    """
    time: float
    kind: Literal["cushion", "collision", "pocket"]
    ball_ids: tuple[str, ...]
    detail: str | None = None


@dataclass
class SimulationResult:
    """Final balls, ordered event log, and total elapsed sim time.

    `pocketed` lists the IDs of balls that entered a pocket. Their entries
    in `final_balls` are frozen at the pocket center with zero motion.
    """
    final_balls: list[Ball]
    events: tuple[SimEvent, ...]
    total_time: float
    pocketed: tuple[str, ...] = ()


_TIME_EVENT_EPS: float = 1e-9


def simulate(state: TableState, max_time: float = 60.0) -> SimulationResult:
    """Evolve all balls from the given state until every ball is at rest.

    The loop is event-driven. Within each ball's current phase (sliding or
    rolling), position is a quadratic in time, so cushion contacts solve as
    quadratic roots and ball-ball collisions as quartic roots. Each iteration:

    1. Detect the earliest cushion or ball-ball event valid within all
       current phases, capped by the soonest phase transition.
    2. Advance every ball analytically (via `step_free_flight`) to that time.
    3. Apply the triggering impulse (`cushion_rebound` or `ball_collision`).
    4. Repeat.

    Phase transitions are not recorded as events — they are only a
    bookkeeping boundary for the quadratic trajectory segments.

    Residual vertical spin is drained after horizontal motion ceases, so the
    final state has all balls truly at rest (within the rest thresholds).

    Parameters
    ----------
    state : TableState
        Initial conditions. Not mutated.
    max_time : float
        Safety clamp. If real-world motion exceeds this, the simulation
        returns with whatever balls are still moving — physical shots always
        settle in a few seconds.
    """
    balls: list[Ball] = [
        _clone(b, b.position.copy(), b.velocity.copy(), b.angular_velocity.copy())
        for b in state.balls
    ]
    table = state.table
    pockets = table.pockets
    pocket_radius = table.pocket_mouth_m
    events: list[SimEvent] = []
    pocketed: set[str] = set()
    t_elapsed = 0.0

    while t_elapsed < max_time:
        moving = [
            i for i, b in enumerate(balls)
            if b.id not in pocketed and _has_horizontal_motion(b)
        ]
        if not moving:
            break

        phase_ends = [_time_to_phase_end(balls[i], table) for i in moving]
        phase_ends = [t for t in phase_ends if t > _TIME_EVENT_EPS]
        if not phase_ends:
            break
        t_cap = min(min(phase_ends), max_time - t_elapsed)

        candidates: list[tuple[float, str, int, int | str]] = []

        for i in moving:
            for rail in RAIL_OUTWARD_NORMALS:
                t_ev = _time_to_cushion(balls[i], rail, table)
                if t_ev is not None and _TIME_EVENT_EPS < t_ev <= t_cap + _TIME_EVENT_EPS:
                    candidates.append((t_ev, "cushion", i, rail))
            for pocket_name, pocket_pos in pockets.items():
                t_ev = _time_to_pocket(balls[i], pocket_pos, pocket_radius, table)
                if t_ev is not None and _TIME_EVENT_EPS < t_ev <= t_cap + _TIME_EVENT_EPS:
                    candidates.append((t_ev, "pocket", i, pocket_name))

        n = len(balls)
        for i in range(n):
            if balls[i].id in pocketed:
                continue
            for j in range(i + 1, n):
                if balls[j].id in pocketed:
                    continue
                if not _has_horizontal_motion(balls[i]) and not _has_horizontal_motion(balls[j]):
                    continue
                t_ev = _time_to_ball_ball(balls[i], balls[j], table)
                if t_ev is not None and _TIME_EVENT_EPS < t_ev <= t_cap + _TIME_EVENT_EPS:
                    candidates.append((t_ev, "collision", i, j))

        if candidates:
            t_next = min(c[0] for c in candidates)
            balls = [step_free_flight(b, t_next, table) for b in balls]
            t_elapsed += t_next

            for candidate in sorted(
                (c for c in candidates if c[0] <= t_next + _TIME_EVENT_EPS),
                key=lambda c: c[0],
            ):
                _apply_event(candidate, balls, events, pocketed, table, pockets, t_elapsed)
        else:
            # No impulse event before the nearest phase change; advance to it.
            balls = [step_free_flight(b, t_cap, table) for b in balls]
            t_elapsed += t_cap

    # Drain residual vertical spin.
    t_spin_stop = max(
        (_time_to_vertical_spin_stop(b, table) for b in balls),
        default=0.0,
    )
    if t_spin_stop > 0.0:
        advance = min(t_spin_stop, max_time - t_elapsed)
        balls = [step_free_flight(b, advance, table) for b in balls]
        t_elapsed += advance

    return SimulationResult(
        final_balls=balls,
        events=tuple(events),
        total_time=t_elapsed,
        pocketed=tuple(b.id for b in balls if b.id in pocketed),
    )


def _apply_event(
    candidate: tuple,
    balls: list[Ball],
    events: list[SimEvent],
    pocketed: set[str],
    table: Table,
    pockets: dict[str, np.ndarray],
    t_abs: float,
) -> None:
    """Apply one detected event in place, with a validity re-check.

    When multiple events share a tick (rare — corner hit, kiss shot), the
    first applied event may invalidate later ones (ball has already moved
    away, balls now separating). Skipping invalid events keeps the simulation
    consistent without ordering ambiguity.
    """
    kind = candidate[1]

    if kind == "cushion":
        _, _, i, rail = candidate
        if balls[i].id in pocketed:
            return
        normal = RAIL_OUTWARD_NORMALS[rail]
        if float(balls[i].velocity @ normal) < 0.0:
            balls[i] = cushion_rebound(balls[i], rail, table)
            events.append(SimEvent(
                time=t_abs, kind="cushion",
                ball_ids=(balls[i].id,), detail=rail,
            ))
    elif kind == "pocket":
        _, _, i, pocket_name = candidate
        if balls[i].id in pocketed:
            return
        # Freeze the ball at the pocket's center so the final state reads
        # cleanly ("this ball is in this pocket"). Motion is zero'd.
        pocket_pos = pockets[pocket_name]
        balls[i] = _clone(
            balls[i],
            pos=pocket_pos.copy(),
            vel=np.zeros(2),
            w=np.zeros(3),
        )
        pocketed.add(balls[i].id)
        events.append(SimEvent(
            time=t_abs, kind="pocket",
            ball_ids=(balls[i].id,), detail=pocket_name,
        ))
    else:  # collision
        _, _, i, j = candidate
        if balls[i].id in pocketed or balls[j].id in pocketed:
            return
        r = balls[j].position - balls[i].position
        dist = float(np.linalg.norm(r))
        if dist <= 0.0:
            return
        n_ij = r / dist
        u_n = float((balls[i].velocity - balls[j].velocity) @ n_ij)
        if u_n > 0.0:
            new_a, new_b = ball_collision(balls[i], balls[j], table)
            balls[i] = new_a
            balls[j] = new_b
            events.append(SimEvent(
                time=t_abs, kind="collision",
                ball_ids=(balls[i].id, balls[j].id),
            ))


def _has_horizontal_motion(ball: Ball) -> bool:
    return float(np.linalg.norm(ball.velocity)) > _V_EPS or float(
        np.linalg.norm(contact_slip(ball.velocity, ball.angular_velocity, ball.radius_m))
    ) > _SLIP_EPS


def _time_to_phase_end(ball: Ball, table: Table) -> float:
    """Time until the ball's current free-flight phase boundary (transition or stop)."""
    R = ball.radius_m
    g = GRAVITY_M_S2
    slip = contact_slip(ball.velocity, ball.angular_velocity, R)
    slip_mag = float(np.linalg.norm(slip))
    if slip_mag > _SLIP_EPS:
        return slip_mag / (3.5 * table.cloth_sliding_friction * g)
    v_mag = float(np.linalg.norm(ball.velocity))
    if v_mag > _V_EPS:
        return v_mag / (table.cloth_rolling_friction * g)
    return 0.0


def _time_to_vertical_spin_stop(ball: Ball, table: Table) -> float:
    wz = abs(float(ball.angular_velocity[2]))
    if wz <= _WZ_EPS:
        return 0.0
    alpha = 2.5 * table.cloth_spinning_friction * GRAVITY_M_S2 / ball.radius_m
    return wz / alpha


def _trajectory_coeffs(
    ball: Ball, table: Table
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (p0, v, a) such that p(t) = p0 + v·t + ½·a·t² within the current phase.

    The acceleration vector is fixed within a phase (slip direction for
    sliding, velocity direction for rolling, zero for stopped), which is
    what makes cushion and ball-ball event times analytic.
    """
    R = ball.radius_m
    g = GRAVITY_M_S2
    slip = contact_slip(ball.velocity, ball.angular_velocity, R)
    slip_mag = float(np.linalg.norm(slip))
    if slip_mag > _SLIP_EPS:
        u_hat = slip / slip_mag
        a = -table.cloth_sliding_friction * g * u_hat
    else:
        v_mag = float(np.linalg.norm(ball.velocity))
        if v_mag > _V_EPS:
            v_hat = ball.velocity / v_mag
            a = -table.cloth_rolling_friction * g * v_hat
        else:
            a = np.zeros(2)
    return ball.position.copy(), ball.velocity.copy(), a


def _time_to_cushion(ball: Ball, rail: str, table: Table) -> float | None:
    p0, v, a = _trajectory_coeffs(ball, table)
    R = ball.radius_m

    if rail == "bottom":
        target, axis = R, 1
    elif rail == "top":
        target, axis = table.length_m - R, 1
    elif rail == "left":
        target, axis = R, 0
    elif rail == "right":
        target, axis = table.width_m - R, 0
    else:
        raise ValueError(f"unknown rail {rail!r}")

    c2 = 0.5 * float(a[axis])
    c1 = float(v[axis])
    c0 = float(p0[axis]) - target
    return _smallest_positive_root([c2, c1, c0])


def _time_to_pocket(
    ball: Ball, pocket_pos: np.ndarray, pocket_radius: float, table: Table
) -> float | None:
    """Time until the ball's center crosses into the pocket zone."""
    p0, v, a = _trajectory_coeffs(ball, table)

    d0 = p0 - pocket_pos
    du = v
    dw = 0.5 * a

    c4 = float(dw @ dw)
    c3 = 2.0 * float(du @ dw)
    c2 = float(du @ du) + 2.0 * float(d0 @ dw)
    c1 = 2.0 * float(d0 @ du)
    c0 = float(d0 @ d0) - pocket_radius * pocket_radius

    if c0 <= 0.0:
        # Already inside the pocket zone at t=0 — skip, avoid re-triggering.
        return None
    return _smallest_positive_root([c4, c3, c2, c1, c0])


def _time_to_ball_ball(a: Ball, b: Ball, table: Table) -> float | None:
    p0_a, v_a, a_a = _trajectory_coeffs(a, table)
    p0_b, v_b, a_b = _trajectory_coeffs(b, table)

    d0 = p0_a - p0_b
    du = v_a - v_b
    dw = 0.5 * (a_a - a_b)
    R_sum = a.radius_m + b.radius_m

    c4 = float(dw @ dw)
    c3 = 2.0 * float(du @ dw)
    c2 = float(du @ du) + 2.0 * float(d0 @ dw)
    c1 = 2.0 * float(d0 @ du)
    c0 = float(d0 @ d0) - R_sum * R_sum

    return _smallest_positive_root([c4, c3, c2, c1, c0])


def _smallest_positive_root(coeffs: list[float]) -> float | None:
    """Smallest strictly positive real root of a polynomial (descending powers)."""
    while coeffs and abs(coeffs[0]) < 1e-15:
        coeffs = coeffs[1:]
    if len(coeffs) < 2:
        return None
    if len(coeffs) == 2:
        # Linear case avoids the numpy.roots companion-matrix overhead.
        slope, intercept = coeffs
        if abs(slope) < 1e-15:
            return None
        t = -intercept / slope
        return t if t > _TIME_EVENT_EPS else None

    roots = np.roots(coeffs)
    positive = [
        float(r.real)
        for r in roots
        if abs(r.imag) < 1e-9 and float(r.real) > _TIME_EVENT_EPS
    ]
    return min(positive) if positive else None
