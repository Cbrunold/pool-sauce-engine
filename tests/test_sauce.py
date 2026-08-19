"""Tests for Unit D — the Sauce translator."""
from __future__ import annotations

import math

import numpy as np
import pytest

from poolsauce import (
    BALL_RADIUS_M,
    SAUCE_ENGLISH,
    SAUCE_STROKE,
    TIP_FRACTION_OF_R,
    Ball,
    SaucePrescription,
    Table,
    TableState,
    angular_velocity_to_tip_offsets,
    cue_state_from_sauce,
    describe_stroke,
    simulate,
    stroke_to_cue_state,
    tip_offsets_from_phrases,
)


def _cue(position=(0.5, 0.5)) -> Ball:
    return Ball(id="cue", position=np.asarray(position, dtype=float))


class TestVocabularySanity:
    def test_stroke_vocab_includes_core_phrases(self) -> None:
        for phrase in (
            "spoon of stun",
            "zest of follow",
            "full follow",
            "whisper of draw",
            "full draw",
        ):
            assert phrase in SAUCE_STROKE

    def test_english_vocab_includes_core_phrases(self) -> None:
        for phrase in (
            "none",
            "pinch of right",
            "pinch of left",
            "drop of right",
            "drop of left",
            "healthy pour of right",
            "healthy pour of left",
        ):
            assert phrase in SAUCE_ENGLISH

    def test_stun_is_zero(self) -> None:
        assert SAUCE_STROKE["spoon of stun"] == 0.0
        assert SAUCE_ENGLISH["none"] == 0.0

    def test_symmetric_pairs_cancel(self) -> None:
        for left, right in (
            ("pinch of left", "pinch of right"),
            ("drop of left", "drop of right"),
            ("healthy pour of left", "healthy pour of right"),
        ):
            assert SAUCE_ENGLISH[left] == -SAUCE_ENGLISH[right]


class TestStrokeToCueState:
    def test_stun_produces_zero_spin(self) -> None:
        cue = stroke_to_cue_state(_cue(), direction=(0.0, 1.0), speed_m_s=1.5)
        np.testing.assert_allclose(cue.velocity, [0.0, 1.5], atol=1e-12)
        np.testing.assert_allclose(cue.angular_velocity, [0.0, 0.0, 0.0], atol=1e-12)

    def test_pure_follow_gives_forward_topspin(self) -> None:
        R = BALL_RADIUS_M
        cue = stroke_to_cue_state(
            _cue(), direction=(0.0, 1.0), speed_m_s=1.0,
            vertical_tips=1.0,
        )
        # For +y stroke with follow, the rolling axis is -x (ω_x < 0 for +y motion).
        assert cue.angular_velocity[0] < 0.0
        assert math.isclose(float(cue.angular_velocity[1]), 0.0, abs_tol=1e-12)
        assert cue.angular_velocity[2] == 0.0
        expected = -2.5 * 1.0 * (1.0 * TIP_FRACTION_OF_R * R) / (R * R)
        np.testing.assert_allclose(cue.angular_velocity[0], expected, atol=1e-12)

    def test_pure_draw_gives_backward_spin(self) -> None:
        R = BALL_RADIUS_M
        cue = stroke_to_cue_state(
            _cue(), direction=(0.0, 1.0), speed_m_s=1.0,
            vertical_tips=-1.0,
        )
        assert cue.angular_velocity[0] > 0.0  # opposite of topspin
        assert cue.angular_velocity[2] == 0.0

    def test_right_english_gives_positive_wz(self) -> None:
        cue = stroke_to_cue_state(
            _cue(), direction=(0.0, 1.0), speed_m_s=1.0,
            horizontal_tips=+1.0,
        )
        assert cue.angular_velocity[2] > 0.0
        assert cue.angular_velocity[0] == 0.0
        assert cue.angular_velocity[1] == 0.0

    def test_left_english_gives_negative_wz(self) -> None:
        cue = stroke_to_cue_state(
            _cue(), direction=(0.0, 1.0), speed_m_s=1.0,
            horizontal_tips=-1.0,
        )
        assert cue.angular_velocity[2] < 0.0

    def test_combined_offsets_produce_full_vector(self) -> None:
        cue = stroke_to_cue_state(
            _cue(), direction=(0.0, 1.0), speed_m_s=2.0,
            vertical_tips=0.5, horizontal_tips=0.5,
        )
        assert cue.angular_velocity[0] < 0.0
        assert cue.angular_velocity[2] > 0.0

    def test_arbitrary_direction_rotates_vertical_axis(self) -> None:
        # Stroke at 45° in the plane. Vertical-english axis should rotate with it.
        cue = stroke_to_cue_state(
            _cue(),
            direction=(1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0)),
            speed_m_s=1.0,
            vertical_tips=1.0,
        )
        # Axis is ẑ × d̂ = (-d_y, d_x, 0) = (-0.707, 0.707, 0).
        # Magnitude check:
        axis_mag = float(np.linalg.norm(cue.angular_velocity[:2]))
        assert axis_mag > 0.0
        # Direction check: proportional to (-1, 1).
        ratio_x = cue.angular_velocity[0] / axis_mag
        ratio_y = cue.angular_velocity[1] / axis_mag
        np.testing.assert_allclose([ratio_x, ratio_y], [-1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0)], atol=1e-9)

    def test_zero_speed_produces_stationary_ball(self) -> None:
        cue = stroke_to_cue_state(
            _cue(), direction=(1.0, 0.0), speed_m_s=0.0,
            vertical_tips=1.0, horizontal_tips=1.0,
        )
        assert cue.is_stationary

    def test_non_unit_direction_rejected(self) -> None:
        with pytest.raises(ValueError, match="unit"):
            stroke_to_cue_state(_cue(), direction=(1.0, 1.0), speed_m_s=1.0)

    def test_negative_speed_rejected(self) -> None:
        with pytest.raises(ValueError, match="speed"):
            stroke_to_cue_state(_cue(), direction=(0.0, 1.0), speed_m_s=-1.0)

    def test_input_cue_not_mutated(self) -> None:
        cue = _cue((0.3, 0.4))
        pos0 = cue.position.copy()
        vel0 = cue.velocity.copy()
        w0 = cue.angular_velocity.copy()
        _ = stroke_to_cue_state(cue, (0.0, 1.0), 1.0, vertical_tips=0.5)
        np.testing.assert_array_equal(cue.position, pos0)
        np.testing.assert_array_equal(cue.velocity, vel0)
        np.testing.assert_array_equal(cue.angular_velocity, w0)


class TestDescribeAndLookup:
    def test_describe_exact_values_round_trip(self) -> None:
        r = describe_stroke(vertical_tips=1.0, horizontal_tips=-0.5)
        assert r.stroke == "full follow"
        assert r.english == "drop of left"
        assert r.vertical_tips == 1.0
        assert r.horizontal_tips == -0.5

    def test_describe_nearest_snaps_to_closest(self) -> None:
        r = describe_stroke(vertical_tips=0.22, horizontal_tips=0.48)
        assert r.stroke == "zest of follow"  # 0.25
        assert r.english == "drop of right"  # 0.50

    def test_describe_zero_is_stun(self) -> None:
        r = describe_stroke(0.0, 0.0)
        assert r.stroke == "spoon of stun"
        assert r.english == "none"

    def test_tip_offsets_from_phrases(self) -> None:
        v, h = tip_offsets_from_phrases(english="pinch of right", stroke="full draw")
        assert v == -1.0
        assert h == 0.25

    def test_unknown_stroke_raises(self) -> None:
        with pytest.raises(KeyError, match="unknown stroke"):
            tip_offsets_from_phrases(english="none", stroke="nightmare shot")

    def test_unknown_english_raises(self) -> None:
        with pytest.raises(KeyError, match="unknown english"):
            tip_offsets_from_phrases(english="moonshot", stroke="spoon of stun")


class TestCueStateFromSauce:
    def test_stun_and_none_equal_zero_spin(self) -> None:
        cue = cue_state_from_sauce(_cue(), (0.0, 1.0), 1.0)
        np.testing.assert_allclose(cue.angular_velocity, [0.0, 0.0, 0.0], atol=1e-12)

    def test_full_follow_matches_stroke_to_cue_state(self) -> None:
        direct = stroke_to_cue_state(_cue(), (0.0, 1.0), 1.5, vertical_tips=1.0)
        via_sauce = cue_state_from_sauce(_cue(), (0.0, 1.0), 1.5, stroke="full follow")
        np.testing.assert_allclose(via_sauce.angular_velocity, direct.angular_velocity, atol=1e-12)
        np.testing.assert_allclose(via_sauce.velocity, direct.velocity, atol=1e-12)

    def test_pinch_of_right_matches_stroke_to_cue_state(self) -> None:
        direct = stroke_to_cue_state(_cue(), (0.0, 1.0), 1.5, horizontal_tips=0.25)
        via = cue_state_from_sauce(_cue(), (0.0, 1.0), 1.5, english="pinch of right")
        np.testing.assert_allclose(via.angular_velocity, direct.angular_velocity, atol=1e-12)


class TestInverseFromAngularVelocity:
    def test_round_trip_sauce_to_omega_and_back(self) -> None:
        direction = np.array([0.0, 1.0])
        speed = 2.0
        v_tips_in, h_tips_in = 0.75, -0.33

        cue = stroke_to_cue_state(
            _cue(), direction, speed,
            vertical_tips=v_tips_in, horizontal_tips=h_tips_in,
        )
        v_out, h_out = angular_velocity_to_tip_offsets(
            cue.angular_velocity, direction, speed, cue.radius_m
        )
        assert math.isclose(v_out, v_tips_in, abs_tol=1e-9)
        assert math.isclose(h_out, h_tips_in, abs_tol=1e-9)

    def test_inverse_requires_positive_speed(self) -> None:
        with pytest.raises(ValueError, match="speed"):
            angular_velocity_to_tip_offsets(
                np.zeros(3), np.array([1.0, 0.0]), 0.0, BALL_RADIUS_M
            )


class TestBehaviorInSimulation:
    """Sauce has the right physical consequences on a cue rolling through cloth.

    Kept under 0.6 m/s so the ball comes to rest well before any rail, so we
    see the stop-distance ordering without cushion-dynamics confounders.
    """

    def _stop_distance(self, stroke_phrase: str, speed: float = 0.5) -> float:
        start = np.array([0.635, 0.7])
        cue_ball = Ball(id="cue", position=start)
        cue = cue_state_from_sauce(
            cue_ball, direction=(0.0, 1.0), speed_m_s=speed,
            stroke=stroke_phrase,
        )
        result = simulate(TableState(table=Table(), balls=[cue]))
        return float(result.final_balls[0].position[1] - start[1])

    def test_follow_extends_beyond_stun(self) -> None:
        # Follow reduces contact-point slip, so less energy is lost to
        # sliding friction — the ball rolls farther.
        stun_dy = self._stop_distance("spoon of stun")
        follow_dy = self._stop_distance("full follow")
        assert follow_dy > stun_dy

    def test_draw_shortens_against_stun(self) -> None:
        # Draw backspin amplifies contact-point slip, so more energy bleeds
        # to sliding friction — the ball stops sooner.
        stun_dy = self._stop_distance("spoon of stun")
        draw_dy = self._stop_distance("full draw")
        assert draw_dy < stun_dy

    def test_english_alone_does_not_change_forward_distance(self) -> None:
        # Side english acts only on ω_z, which decays via spinning friction,
        # independent of horizontal motion. Stop distance should be stun.
        stun_dy = self._stop_distance("spoon of stun")
        # Apply right english while keeping stroke = stun.
        start = np.array([0.635, 0.7])
        cue = cue_state_from_sauce(
            Ball(id="cue", position=start), direction=(0.0, 1.0),
            speed_m_s=0.5, english="healthy pour of right", stroke="spoon of stun",
        )
        result = simulate(TableState(table=Table(), balls=[cue]))
        english_dy = float(result.final_balls[0].position[1] - start[1])
        assert math.isclose(english_dy, stun_dy, rel_tol=1e-9)
