"""Tests for Units B.1 (free-flight) and B.2 (cushion rebound)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from poolsauce import (
    BALL_RADIUS_M,
    Ball,
    GRAVITY_M_S2,
    RAIL_OUTWARD_NORMALS,
    Table,
    advance_to_rest,
    ball_collision,
    contact_slip,
    cushion_rebound,
    is_rolling,
    step_free_flight,
)


def _cue(position=(0.5, 1.0), velocity=(0.0, 0.0), angular_velocity=(0.0, 0.0, 0.0)) -> Ball:
    return Ball(
        id="cue",
        position=np.asarray(position, dtype=float),
        velocity=np.asarray(velocity, dtype=float),
        angular_velocity=np.asarray(angular_velocity, dtype=float),
    )


class TestContactSlip:
    def test_stationary_ball_has_zero_slip(self) -> None:
        slip = contact_slip(np.zeros(2), np.zeros(3), BALL_RADIUS_M)
        np.testing.assert_allclose(slip, [0.0, 0.0])

    def test_pure_translation_slips_forward(self) -> None:
        slip = contact_slip(np.array([1.0, 0.0]), np.zeros(3), BALL_RADIUS_M)
        np.testing.assert_allclose(slip, [1.0, 0.0])

    def test_rolling_condition_gives_zero_slip(self) -> None:
        R = BALL_RADIUS_M
        v = np.array([1.0, 0.0])
        # Pure rolling in +x: ω_y = v_x / R.
        w = np.array([0.0, v[0] / R, 0.0])
        np.testing.assert_allclose(
            contact_slip(v, w, R), [0.0, 0.0], atol=1e-12
        )

    def test_vertical_spin_does_not_contribute(self) -> None:
        slip_no_z = contact_slip(np.array([1.0, 0.0]), np.array([0.0, 0.0, 0.0]), BALL_RADIUS_M)
        slip_with_z = contact_slip(np.array([1.0, 0.0]), np.array([0.0, 0.0, 10.0]), BALL_RADIUS_M)
        np.testing.assert_allclose(slip_no_z, slip_with_z)


class TestStepFreeFlightPurity:
    def test_input_ball_not_mutated(self) -> None:
        t = Table()
        b = _cue(velocity=(1.0, 0.0))
        pos_before = b.position.copy()
        vel_before = b.velocity.copy()
        w_before = b.angular_velocity.copy()

        _ = step_free_flight(b, 0.5, t)

        np.testing.assert_array_equal(b.position, pos_before)
        np.testing.assert_array_equal(b.velocity, vel_before)
        np.testing.assert_array_equal(b.angular_velocity, w_before)

    def test_zero_dt_returns_copy(self) -> None:
        t = Table()
        b = _cue(velocity=(1.0, 0.0))
        out = step_free_flight(b, 0.0, t)
        assert out is not b
        np.testing.assert_array_equal(out.position, b.position)
        np.testing.assert_array_equal(out.velocity, b.velocity)
        np.testing.assert_array_equal(out.angular_velocity, b.angular_velocity)

    def test_negative_dt_rejected(self) -> None:
        t = Table()
        b = _cue()
        with pytest.raises(ValueError, match="dt"):
            step_free_flight(b, -0.01, t)


class TestStationary:
    def test_stationary_ball_stays_put(self) -> None:
        t = Table()
        b = _cue(position=(0.5, 1.0))
        out = step_free_flight(b, 1.0, t)
        np.testing.assert_array_equal(out.position, b.position)
        np.testing.assert_array_equal(out.velocity, np.zeros(2))
        np.testing.assert_array_equal(out.angular_velocity, np.zeros(3))


class TestRollingPhase:
    def test_pure_rolling_decelerates_at_rolling_friction(self) -> None:
        t = Table()
        R = BALL_RADIUS_M
        v0 = 1.0
        # Start in pure rolling along +x.
        b = _cue(velocity=(v0, 0.0), angular_velocity=(0.0, v0 / R, 0.0))

        dt = 0.1
        out = step_free_flight(b, dt, t)
        # Ball stays in rolling; analytic v(dt) = v0 - μ_r g dt.
        expected_v = v0 - t.cloth_rolling_friction * GRAVITY_M_S2 * dt
        np.testing.assert_allclose(out.velocity, [expected_v, 0.0], atol=1e-10)
        # Rolling constraint preserved.
        assert is_rolling(out)

    def test_rolling_ball_stops_at_predicted_time(self) -> None:
        t = Table()
        R = BALL_RADIUS_M
        v0 = 1.0
        b = _cue(velocity=(v0, 0.0), angular_velocity=(0.0, v0 / R, 0.0))

        t_stop = v0 / (t.cloth_rolling_friction * GRAVITY_M_S2)
        out = step_free_flight(b, t_stop + 1.0, t)
        np.testing.assert_allclose(out.velocity, [0.0, 0.0], atol=1e-10)
        np.testing.assert_allclose(out.angular_velocity, [0.0, 0.0, 0.0], atol=1e-10)

    def test_rolling_ball_stops_at_expected_position(self) -> None:
        # Analytic: displacement = v0² / (2 μ_r g)
        t = Table()
        R = BALL_RADIUS_M
        v0 = 1.0
        b = _cue(position=(0.5, 0.5), velocity=(v0, 0.0), angular_velocity=(0.0, v0 / R, 0.0))
        out = advance_to_rest(b, t)
        dx = v0**2 / (2 * t.cloth_rolling_friction * GRAVITY_M_S2)
        np.testing.assert_allclose(out.position, [0.5 + dx, 0.5], atol=1e-9)


class TestSlidingToRolling:
    def test_stun_shot_transitions_to_rolling(self) -> None:
        # Pure translation, zero spin — classic stun. After sliding phase
        # completes, analytic velocity is (5/7) v0 in the original direction.
        t = Table()
        v0 = 2.0
        b = _cue(velocity=(v0, 0.0))
        t_roll = v0 / (3.5 * t.cloth_sliding_friction * GRAVITY_M_S2)

        out = step_free_flight(b, t_roll, t)
        # At the exact moment of rolling transition.
        np.testing.assert_allclose(out.velocity, [5.0 / 7.0 * v0, 0.0], atol=1e-9)
        assert is_rolling(out)

    def test_full_settlement_from_stun(self) -> None:
        t = Table()
        v0 = 2.0
        b = _cue(position=(0.3, 0.4), velocity=(v0, 0.0))
        out = advance_to_rest(b, t)
        np.testing.assert_allclose(out.velocity, [0.0, 0.0], atol=1e-10)
        np.testing.assert_allclose(out.angular_velocity, [0.0, 0.0, 0.0], atol=1e-10)
        assert out.position[0] > 0.3  # moved forward
        assert math.isclose(out.position[1], 0.4, abs_tol=1e-10)


class TestVerticalSpin:
    def test_decays_to_zero_independently(self) -> None:
        t = Table()
        wz0 = 50.0
        b = _cue(angular_velocity=(0.0, 0.0, wz0))
        out = advance_to_rest(b, t)
        assert math.isclose(out.angular_velocity[2], 0.0, abs_tol=1e-10)
        # Ball did not translate.
        np.testing.assert_array_equal(out.position, b.position)
        np.testing.assert_allclose(out.velocity, [0.0, 0.0])

    def test_partial_step_reduces_vertical_spin_linearly(self) -> None:
        t = Table()
        R = BALL_RADIUS_M
        wz0 = 20.0
        alpha = 2.5 * t.cloth_spinning_friction * GRAVITY_M_S2 / R
        dt = 0.01
        b = _cue(angular_velocity=(0.0, 0.0, wz0))

        out = step_free_flight(b, dt, t)
        expected = wz0 - alpha * dt
        np.testing.assert_allclose(out.angular_velocity[2], expected, atol=1e-10)

    def test_vertical_spin_does_not_affect_translation(self) -> None:
        # Rolling ball with vertical spin moves the same as one without.
        t = Table()
        R = BALL_RADIUS_M
        v0 = 1.0
        b_with = _cue(velocity=(v0, 0.0), angular_velocity=(0.0, v0 / R, 5.0))
        b_without = _cue(velocity=(v0, 0.0), angular_velocity=(0.0, v0 / R, 0.0))

        out_with = step_free_flight(b_with, 0.2, t)
        out_without = step_free_flight(b_without, 0.2, t)
        np.testing.assert_allclose(out_with.position, out_without.position, atol=1e-12)
        np.testing.assert_allclose(out_with.velocity, out_without.velocity, atol=1e-12)


class TestCushionRebound:
    def test_head_on_bottom_rail_reverses_and_loses_energy(self) -> None:
        t = Table()
        b = _cue(position=(0.5, 0.1), velocity=(0.0, -1.0))
        out = cushion_rebound(b, "bottom", t)
        expected_v = t.cushion_efficiency * 1.0
        np.testing.assert_allclose(out.velocity, [0.0, expected_v], atol=1e-12)

    def test_head_on_top_rail(self) -> None:
        t = Table()
        b = _cue(position=(0.5, 2.4), velocity=(0.0, 1.0))
        out = cushion_rebound(b, "top", t)
        np.testing.assert_allclose(out.velocity, [0.0, -t.cushion_efficiency], atol=1e-12)

    def test_head_on_left_rail(self) -> None:
        t = Table()
        b = _cue(position=(0.05, 1.0), velocity=(-1.0, 0.0))
        out = cushion_rebound(b, "left", t)
        np.testing.assert_allclose(out.velocity, [t.cushion_efficiency, 0.0], atol=1e-12)

    def test_head_on_right_rail(self) -> None:
        t = Table()
        b = _cue(position=(1.2, 1.0), velocity=(1.0, 0.0))
        out = cushion_rebound(b, "right", t)
        np.testing.assert_allclose(out.velocity, [-t.cushion_efficiency, 0.0], atol=1e-12)

    def test_tangential_retention_at_low_pace(self) -> None:
        # Slow, angled shot at the top rail. k_t at pace=1 is high.
        t = Table()
        b = _cue(position=(0.5, 2.4), velocity=(1.0, 1.0))
        out = cushion_rebound(b, "top", t)
        pace = 1.0
        expected_kt = t.cushion_tangential_retention - t.cushion_tangential_pace_falloff * pace
        np.testing.assert_allclose(out.velocity[0], expected_kt * 1.0, atol=1e-12)
        np.testing.assert_allclose(out.velocity[1], -t.cushion_efficiency * 1.0, atol=1e-12)

    def test_higher_pace_shortens_rebound(self) -> None:
        # Same incoming angle, different speeds. The faster rebound has a
        # smaller tangential-to-normal ratio (bank shortens).
        t = Table()
        slow = _cue(position=(0.5, 2.4), velocity=(1.0, 1.0))
        fast = _cue(position=(0.5, 2.4), velocity=(5.0, 5.0))

        out_slow = cushion_rebound(slow, "top", t)
        out_fast = cushion_rebound(fast, "top", t)

        ratio_slow = abs(out_slow.velocity[0]) / abs(out_slow.velocity[1])
        ratio_fast = abs(out_fast.velocity[0]) / abs(out_fast.velocity[1])
        assert ratio_fast < ratio_slow

    def test_running_english_widens_rebound(self) -> None:
        # Top rail. Post-rebound direction is (+x, -y). Running english for
        # +x motion along the rail is ω_z > 0.
        t = Table()
        neutral = _cue(position=(0.5, 2.4), velocity=(1.0, 1.0))
        running = _cue(position=(0.5, 2.4), velocity=(1.0, 1.0), angular_velocity=(0.0, 0.0, 20.0))

        out_neutral = cushion_rebound(neutral, "top", t)
        out_running = cushion_rebound(running, "top", t)
        assert out_running.velocity[0] > out_neutral.velocity[0]

    def test_reverse_english_shortens_rebound(self) -> None:
        t = Table()
        neutral = _cue(position=(0.5, 2.4), velocity=(1.0, 1.0))
        reverse = _cue(position=(0.5, 2.4), velocity=(1.0, 1.0), angular_velocity=(0.0, 0.0, -20.0))

        out_neutral = cushion_rebound(neutral, "top", t)
        out_reverse = cushion_rebound(reverse, "top", t)
        assert out_reverse.velocity[0] < out_neutral.velocity[0]

    def test_side_english_magnitude_decays(self) -> None:
        t = Table()
        wz0 = 20.0
        b = _cue(position=(0.5, 2.4), velocity=(0.0, 1.0), angular_velocity=(0.0, 0.0, wz0))
        out = cushion_rebound(b, "top", t)
        assert abs(out.angular_velocity[2]) < abs(wz0)
        np.testing.assert_allclose(
            out.angular_velocity[2], wz0 * (1.0 - t.cushion_side_english_loss), atol=1e-12
        )

    def test_horizontal_spin_preserved_through_bounce(self) -> None:
        # Topspin about an axis in the table plane is left alone by the rail —
        # free flight on the cloth handles its post-rebound effect.
        t = Table()
        R = BALL_RADIUS_M
        b = _cue(
            position=(0.5, 2.4),
            velocity=(0.0, 1.0),
            angular_velocity=(1.0 / R, 0.0, 0.0),
        )
        out = cushion_rebound(b, "top", t)
        np.testing.assert_allclose(out.angular_velocity[0], 1.0 / R, atol=1e-12)
        np.testing.assert_allclose(out.angular_velocity[1], 0.0, atol=1e-12)

    def test_ball_moving_away_is_untouched(self) -> None:
        t = Table()
        b = _cue(position=(0.5, 0.1), velocity=(0.0, 1.0), angular_velocity=(0.0, 0.0, 5.0))
        out = cushion_rebound(b, "bottom", t)
        np.testing.assert_array_equal(out.velocity, b.velocity)
        np.testing.assert_array_equal(out.angular_velocity, b.angular_velocity)

    def test_tangential_retention_min_clamp(self) -> None:
        # Absurdly high pace — k_t should clamp to the minimum.
        t = Table()
        huge = 100.0
        b = _cue(position=(0.5, 2.4), velocity=(1.0, huge))
        out = cushion_rebound(b, "top", t)
        # Tangential = k_min * v_t_in; normal = e * v_n_in.
        np.testing.assert_allclose(
            out.velocity[0], t.cushion_tangential_retention_min * 1.0, atol=1e-12
        )

    def test_arbitrary_unit_normal_works(self) -> None:
        # 45° rail (e.g., a corner chamfer). Head-on hit.
        t = Table()
        n = np.array([1.0, 1.0]) / math.sqrt(2.0)
        v_in = -n * 2.0  # straight into it
        b = _cue(position=(0.5, 0.5), velocity=v_in)
        out = cushion_rebound(b, n, t)
        expected = t.cushion_efficiency * 2.0 * n
        np.testing.assert_allclose(out.velocity, expected, atol=1e-10)

    def test_non_unit_normal_rejected(self) -> None:
        t = Table()
        b = _cue(position=(0.5, 2.4), velocity=(0.0, 1.0))
        with pytest.raises(ValueError, match="unit"):
            cushion_rebound(b, np.array([1.0, 1.0]), t)

    def test_unknown_rail_name_rejected(self) -> None:
        t = Table()
        b = _cue(position=(0.5, 2.4), velocity=(0.0, 1.0))
        with pytest.raises(ValueError, match="unknown rail"):
            cushion_rebound(b, "diagonal", t)

    def test_no_mutation_of_input(self) -> None:
        t = Table()
        b = _cue(
            position=(0.5, 2.4),
            velocity=(1.0, 1.0),
            angular_velocity=(1.0, 2.0, 3.0),
        )
        pos0 = b.position.copy()
        vel0 = b.velocity.copy()
        w0 = b.angular_velocity.copy()
        _ = cushion_rebound(b, "top", t)
        np.testing.assert_array_equal(b.position, pos0)
        np.testing.assert_array_equal(b.velocity, vel0)
        np.testing.assert_array_equal(b.angular_velocity, w0)

    def test_all_four_rails_reverse_their_own_axis(self) -> None:
        t = Table()
        for rail, normal in RAIL_OUTWARD_NORMALS.items():
            # Incoming velocity is anti-parallel to the outward normal.
            v_in = -normal * 1.5
            b = _cue(position=(0.5, 1.0), velocity=v_in)
            out = cushion_rebound(b, rail, t)
            expected = t.cushion_efficiency * 1.5 * normal
            np.testing.assert_allclose(out.velocity, expected, atol=1e-10)


def _pair(v_a=(0.0, 1.0), w_a=(0.0, 0.0, 0.0), v_b=(0.0, 0.0), w_b=(0.0, 0.0, 0.0)) -> tuple[Ball, Ball]:
    """Cue at origin, object ball one contact-distance up the +y axis (LoC = +ŷ)."""
    R = BALL_RADIUS_M
    return (
        Ball(id="cue", position=np.array([0.0, 0.0]),
             velocity=np.asarray(v_a, dtype=float),
             angular_velocity=np.asarray(w_a, dtype=float)),
        Ball(id="ob", position=np.array([0.0, 2.0 * R]),
             velocity=np.asarray(v_b, dtype=float),
             angular_velocity=np.asarray(w_b, dtype=float)),
    )


class TestBallCollisionGeometry:
    def test_zero_separation_rejected(self) -> None:
        t = Table()
        a = Ball(id="a", position=np.zeros(2))
        b = Ball(id="b", position=np.zeros(2))
        with pytest.raises(ValueError, match="position"):
            ball_collision(a, b, t)

    def test_separating_pair_unchanged(self) -> None:
        t = Table()
        # Cue below OB, cue moving DOWN — no approach.
        a, b = _pair(v_a=(0.0, -1.0), v_b=(0.0, 0.0))
        out_a, out_b = ball_collision(a, b, t)
        np.testing.assert_array_equal(out_a.velocity, a.velocity)
        np.testing.assert_array_equal(out_b.velocity, b.velocity)
        np.testing.assert_array_equal(out_a.angular_velocity, a.angular_velocity)
        np.testing.assert_array_equal(out_b.angular_velocity, b.angular_velocity)

    def test_no_mutation_of_inputs(self) -> None:
        t = Table()
        a, b = _pair(v_a=(0.2, 1.0), w_a=(1.0, 2.0, 3.0))
        va0 = a.velocity.copy()
        wa0 = a.angular_velocity.copy()
        _ = ball_collision(a, b, t)
        np.testing.assert_array_equal(a.velocity, va0)
        np.testing.assert_array_equal(a.angular_velocity, wa0)


class TestStraightHitNoSpin:
    def test_ob_takes_most_of_velocity_cue_slightly_follows(self) -> None:
        t = Table()
        a, b = _pair(v_a=(0.0, 1.0))
        out_a, out_b = ball_collision(a, b, t)
        # Equal masses, COR e=0.92:
        # v_a_new = (1-e)/2 · v0 = 0.04
        # v_b_new = (1+e)/2 · v0 = 0.96
        np.testing.assert_allclose(out_a.velocity, [0.0, (1 - 0.92) / 2], atol=1e-12)
        np.testing.assert_allclose(out_b.velocity, [0.0, (1 + 0.92) / 2], atol=1e-12)

    def test_elastic_limit_swaps_velocities(self) -> None:
        t = Table(ball_ball_restitution=1.0)
        a, b = _pair(v_a=(0.0, 1.0))
        out_a, out_b = ball_collision(a, b, t)
        np.testing.assert_allclose(out_a.velocity, [0.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(out_b.velocity, [0.0, 1.0], atol=1e-12)

    def test_no_throw_when_no_tangential_slip(self) -> None:
        t = Table()
        a, b = _pair(v_a=(0.0, 1.0))
        out_a, out_b = ball_collision(a, b, t)
        # No tangential velocity or spin exchange.
        assert out_a.velocity[0] == 0.0
        assert out_b.velocity[0] == 0.0
        np.testing.assert_array_equal(out_a.angular_velocity, np.zeros(3))
        np.testing.assert_array_equal(out_b.angular_velocity, np.zeros(3))


class TestCutInducedThrow:
    def test_object_ball_deflects_toward_cue_travel_direction(self) -> None:
        # Cue moving up-and-to-the-right into an OB straight above: the
        # friction at contact drags the OB slightly to the right (direction
        # the cue is traveling along the tangent).
        t = Table()
        a, b = _pair(v_a=(0.5, 1.0))  # tangential slip in +x at contact
        out_a, out_b = ball_collision(a, b, t)
        assert out_b.velocity[0] > 0.0
        assert out_b.velocity[1] > 0.0
        # OB throw is off LoC by a small angle.
        throw = math.degrees(math.atan2(out_b.velocity[0], out_b.velocity[1]))
        assert 0.1 < throw < 10.0

    def test_symmetric_cuts_produce_opposite_throws(self) -> None:
        t = Table()
        a_right, b_right = _pair(v_a=(+0.5, 1.0))
        a_left, b_left = _pair(v_a=(-0.5, 1.0))
        _, ob_r = ball_collision(a_right, b_right, t)
        _, ob_l = ball_collision(a_left, b_left, t)
        assert ob_r.velocity[0] > 0.0
        assert ob_l.velocity[0] < 0.0
        assert math.isclose(ob_r.velocity[0], -ob_l.velocity[0], rel_tol=1e-12)
        assert math.isclose(ob_r.velocity[1], ob_l.velocity[1], rel_tol=1e-12)


class TestSpinInducedThrow:
    def test_side_english_throws_ob_off_line_of_centers(self) -> None:
        # Straight hit (no translational slip) but cue spinning +ω_z.
        # Cue's contact point moves in +t̂ (= -x̂); friction throws OB in +t̂.
        t = Table()
        a, b = _pair(v_a=(0.0, 1.0), w_a=(0.0, 0.0, 20.0))
        _, ob = ball_collision(a, b, t)
        # +ω_z → throw in -x direction.
        assert ob.velocity[0] < 0.0
        # LoC component preserved.
        np.testing.assert_allclose(ob.velocity[1], (1 + 0.92) / 2, atol=1e-12)

    def test_reverse_english_throws_opposite_direction(self) -> None:
        t = Table()
        a_pos, b_pos = _pair(v_a=(0.0, 1.0), w_a=(0.0, 0.0, 20.0))
        a_neg, b_neg = _pair(v_a=(0.0, 1.0), w_a=(0.0, 0.0, -20.0))
        _, ob_pos = ball_collision(a_pos, b_pos, t)
        _, ob_neg = ball_collision(a_neg, b_neg, t)
        assert ob_pos.velocity[0] < 0.0
        assert ob_neg.velocity[0] > 0.0
        assert math.isclose(ob_pos.velocity[0], -ob_neg.velocity[0], abs_tol=1e-12)


class TestSpinTransferAndCueDeflection:
    def test_cue_deflects_opposite_to_ob_throw(self) -> None:
        t = Table()
        a, b = _pair(v_a=(0.0, 1.0), w_a=(0.0, 0.0, 20.0))
        cue, ob = ball_collision(a, b, t)
        assert cue.velocity[0] > 0.0  # cue deflects in +x
        assert ob.velocity[0] < 0.0   # OB thrown in -x
        # Tangential momentum conservation (no external impulse during collision).
        assert math.isclose(cue.velocity[0] + ob.velocity[0], 0.0, abs_tol=1e-12)

    def test_ob_picks_up_spin_opposite_to_cue(self) -> None:
        # Documented pool behavior: spin partially "transfers" in the opposite
        # sense. Cue +ω_z → OB gains -ω_z (slightly).
        t = Table()
        a, b = _pair(v_a=(0.0, 1.0), w_a=(0.0, 0.0, 20.0))
        cue, ob = ball_collision(a, b, t)
        assert ob.angular_velocity[2] < 0.0
        # And the cue's spin magnitude is reduced.
        assert 0.0 < cue.angular_velocity[2] < 20.0

    def test_horizontal_spin_does_not_affect_ob_path(self) -> None:
        # Topspin on the cue (ω_x or ω_y) is absorbed by the cloth constraint
        # at contact; it does not deflect the OB in-plane.
        t = Table()
        R = BALL_RADIUS_M
        topspin = 1.0 / R
        a_no, b_no = _pair(v_a=(0.0, 1.0))
        a_top, b_top = _pair(v_a=(0.0, 1.0), w_a=(topspin, 0.0, 0.0))
        _, ob_no = ball_collision(a_no, b_no, t)
        _, ob_top = ball_collision(a_top, b_top, t)
        np.testing.assert_allclose(ob_top.velocity, ob_no.velocity, atol=1e-12)


class TestConservation:
    def test_linear_momentum_conserved(self) -> None:
        t = Table()
        a, b = _pair(v_a=(0.3, 1.0), w_a=(0.0, 0.0, 15.0))
        p_before = a.mass_kg * a.velocity + b.mass_kg * b.velocity
        out_a, out_b = ball_collision(a, b, t)
        p_after = out_a.mass_kg * out_a.velocity + out_b.mass_kg * out_b.velocity
        np.testing.assert_allclose(p_after, p_before, atol=1e-12)

    def test_energy_not_increased(self) -> None:
        # With e < 1 and sliding friction at contact, kinetic energy can
        # only decrease.
        t = Table()
        a, b = _pair(v_a=(0.3, 1.2), w_a=(0.5, -0.5, 10.0))
        R = BALL_RADIUS_M
        I_a = 0.4 * a.mass_kg * R * R
        I_b = 0.4 * b.mass_kg * R * R

        def ke(ba, bb):
            lin = 0.5 * ba.mass_kg * float(ba.velocity @ ba.velocity) + 0.5 * bb.mass_kg * float(bb.velocity @ bb.velocity)
            rot = 0.5 * I_a * float(ba.angular_velocity @ ba.angular_velocity) + 0.5 * I_b * float(bb.angular_velocity @ bb.angular_velocity)
            return lin + rot

        out_a, out_b = ball_collision(a, b, t)
        assert ke(out_a, out_b) <= ke(a, b) + 1e-12

    def test_loc_relative_velocity_reversed_by_e(self) -> None:
        # Along the line of centers, (u_n_after) = -e · u_n_before.
        t = Table()
        a, b = _pair(v_a=(0.2, 1.3), w_a=(0.0, 0.0, 5.0))
        out_a, out_b = ball_collision(a, b, t)
        n = np.array([0.0, 1.0])
        u_before = float((a.velocity - b.velocity) @ n)
        u_after = float((out_a.velocity - out_b.velocity) @ n)
        np.testing.assert_allclose(u_after, -t.ball_ball_restitution * u_before, atol=1e-12)


class TestArbitraryGeometry:
    def test_diagonal_line_of_centers(self) -> None:
        # OB off-axis: LoC at 45° above +x axis.
        t = Table()
        R = BALL_RADIUS_M
        n = np.array([1.0, 1.0]) / math.sqrt(2.0)
        a = Ball(id="cue", position=np.zeros(2), velocity=n * 1.0)
        b = Ball(id="ob", position=2 * R * n)
        out_a, out_b = ball_collision(a, b, t)
        # Straight-on along LoC, no spin: OB velocity is along +n̂.
        expected_b = (1 + t.ball_ball_restitution) / 2 * n
        np.testing.assert_allclose(out_b.velocity, expected_b, atol=1e-12)
        expected_a = (1 - t.ball_ball_restitution) / 2 * n
        np.testing.assert_allclose(out_a.velocity, expected_a, atol=1e-12)

    def test_unequal_masses_distribute_impulse_correctly(self) -> None:
        # Heavy OB at rest hit by light cue moving straight in.
        t = Table(ball_ball_restitution=1.0)
        R = BALL_RADIUS_M
        a = Ball(id="cue", position=np.zeros(2), velocity=np.array([0.0, 1.0]), mass_kg=0.100)
        b = Ball(id="ob", position=np.array([0.0, 2.0 * R]), mass_kg=0.300)
        out_a, out_b = ball_collision(a, b, t)
        # Analytic 1D elastic, m_a=1, m_b=3, v_a=1, v_b=0:
        # v_a' = (m_a - m_b)/(m_a + m_b) · v_a = -1/2
        # v_b' = 2·m_a/(m_a + m_b) · v_a = 1/2
        np.testing.assert_allclose(out_a.velocity, [0.0, -0.5], atol=1e-12)
        np.testing.assert_allclose(out_b.velocity, [0.0, 0.5], atol=1e-12)
