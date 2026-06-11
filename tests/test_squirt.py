"""Tests for the squirt (cue-ball deflection) model.

Squirt: side english strikes the ball off-center; the cue's endmass throws
the cue ball off the stick's aim line, toward the side OPPOSITE the english.
Modeled by the natural pivot length: tan(squirt) = tip_offset / pivot_length.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from poolsauce import (
    BALL_RADIUS_M,
    TIP_FRACTION_OF_R,
    Ball,
    Table,
    TableState,
    aim_for_cue_path,
    compose_pillar_plan,
    Intention,
    SauceChoice,
    squirt_angle_rad,
    stroke_to_cue_state,
)


def _cue(position=(0.5, 0.5)) -> Ball:
    return Ball(id="cue", position=np.asarray(position, dtype=float))


PIVOT = 0.279  # default natural pivot length (m)


class TestSquirtAngle:
    def test_no_english_no_squirt(self) -> None:
        assert squirt_angle_rad(0.0, BALL_RADIUS_M, PIVOT) == 0.0

    def test_matches_pivot_length_geometry(self) -> None:
        # tan(squirt) = b / pivot, with b = tips * TIP_FRACTION_OF_R * R
        tips = 1.0
        b = tips * TIP_FRACTION_OF_R * BALL_RADIUS_M
        expected = math.atan2(b, PIVOT)
        assert squirt_angle_rad(tips, BALL_RADIUS_M, PIVOT) == pytest.approx(expected)

    def test_realistic_magnitude_is_small(self) -> None:
        # One full tip of english should squirt on the order of ~1 degree.
        deg = math.degrees(squirt_angle_rad(1.0, BALL_RADIUS_M, PIVOT))
        assert 0.5 < deg < 2.5

    def test_sign_follows_english(self) -> None:
        right = squirt_angle_rad(+0.5, BALL_RADIUS_M, PIVOT)
        left = squirt_angle_rad(-0.5, BALL_RADIUS_M, PIVOT)
        assert right > 0 and left < 0
        assert right == pytest.approx(-left)


class TestStrokeDeflection:
    def test_squirt_off_by_default(self) -> None:
        # Without a pivot length, velocity follows the stick line exactly.
        cue = _cue()
        d = np.array([0.0, 1.0])
        ball = stroke_to_cue_state(cue, d, 2.0, horizontal_tips=1.0)
        vdir = ball.velocity / np.linalg.norm(ball.velocity)
        assert vdir == pytest.approx(d)

    def test_right_english_deflects_cue_left(self) -> None:
        # Stroke along +y; right english should deflect the path toward -x (left).
        cue = _cue()
        d = np.array([0.0, 1.0])
        ball = stroke_to_cue_state(
            cue, d, 2.0, horizontal_tips=+1.0, squirt_pivot_length_m=PIVOT
        )
        vdir = ball.velocity / np.linalg.norm(ball.velocity)
        assert vdir[0] < 0.0  # deflected to the left of +y
        ang = math.atan2(vdir[0], vdir[1])  # signed angle from +y
        assert abs(ang) == pytest.approx(
            squirt_angle_rad(1.0, BALL_RADIUS_M, PIVOT), abs=1e-9
        )

    def test_left_english_deflects_cue_right(self) -> None:
        cue = _cue()
        d = np.array([0.0, 1.0])
        ball = stroke_to_cue_state(
            cue, d, 2.0, horizontal_tips=-1.0, squirt_pivot_length_m=PIVOT
        )
        vdir = ball.velocity / np.linalg.norm(ball.velocity)
        assert vdir[0] > 0.0  # deflected to the right of +y

    def test_spin_unaffected_by_squirt(self) -> None:
        # ω_z is set by the tip offset, independent of the path deflection.
        cue = _cue()
        d = np.array([0.0, 1.0])
        plain = stroke_to_cue_state(cue, d, 2.0, horizontal_tips=1.0)
        squirted = stroke_to_cue_state(
            cue, d, 2.0, horizontal_tips=1.0, squirt_pivot_length_m=PIVOT
        )
        assert squirted.angular_velocity[2] == pytest.approx(
            plain.angular_velocity[2]
        )


class TestAimCompensationRoundTrip:
    def test_compensated_stick_lands_ball_on_path(self) -> None:
        # Aim compensation + squirt deflection should cancel: the ball ends up
        # travelling the desired path direction.
        cue = _cue()
        desired = np.array([0.0, 1.0])
        for tips in (-1.0, -0.5, 0.25, 1.0):
            stick = aim_for_cue_path(desired, tips, BALL_RADIUS_M, PIVOT)
            stick = stick / np.linalg.norm(stick)
            ball = stroke_to_cue_state(
                cue, stick, 2.0, horizontal_tips=tips, squirt_pivot_length_m=PIVOT
            )
            vdir = ball.velocity / np.linalg.norm(ball.velocity)
            assert vdir == pytest.approx(desired, abs=1e-9)


class TestComposerExposesSquirt:
    def _state(self) -> TableState:
        table = Table()
        return TableState(
            table=table,
            balls=[
                Ball(id="cue", position=np.array([0.6, 0.5])),
                Ball(id="1", position=np.array([0.7, 1.6])),
            ],
        )

    def test_plan_exposes_squirt_with_english(self) -> None:
        plan = compose_pillar_plan(
            self._state(),
            "shot-squirt",
            Intention(
                target_ball_id="1",
                pocket="top-right",
                destination_descriptor="center",
            ),
            SauceChoice(english="healthy pour of right", stroke="spoon of stun"),
        )
        loa = plan["pillar_II"]["line_of_aim"]
        assert "squirt_deg" in loa
        assert "stick_aim_vector" in loa
        assert abs(loa["squirt_deg"]) > 0.0

    def test_plan_no_squirt_field_without_english(self) -> None:
        plan = compose_pillar_plan(
            self._state(),
            "shot-center",
            Intention(
                target_ball_id="1",
                pocket="top-right",
                destination_descriptor="center",
            ),
            SauceChoice(english="none", stroke="spoon of stun"),
        )
        loa = plan["pillar_II"]["line_of_aim"]
        assert "squirt_deg" not in loa
