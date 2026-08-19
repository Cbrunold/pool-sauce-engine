"""Validation of the 30-degree rule (Dr. Dave TP 3.3 / A-series).

The 30-degree rule: a ROLLING (natural follow) cue ball, over a range of cut
angles near a half-ball hit, deflects roughly 30 degrees from its original
direction once it settles back into a roll after contact.

This is an EMERGENT property of the engine, not a hard-coded rule. The test
fires a rolling cue into a resting object ball at a known cut angle, resolves
the collision, then lets the cue re-establish roll under cloth friction and
measures the settled deflection. If the impulse + free-flight models are
calibrated correctly, the answer lands near 30 degrees.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from poolsauce import (
    BALL_RADIUS_M,
    Ball,
    Table,
    ball_collision,
    is_rolling,
    step_free_flight,
)


def _deg_between(v: np.ndarray, ref: np.ndarray) -> float:
    """Unsigned angle in degrees between two 2D vectors."""
    cosang = float(np.dot(v, ref) / (np.linalg.norm(v) * np.linalg.norm(ref)))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosang))))


def _settled_deflection(cut_angle_deg: float, speed: float = 2.5) -> tuple[float, float]:
    """Fire a rolling cue at a resting OB; return (immediate, settled) deflection.

    immediate — the post-collision tangent deflection (before roll re-asserts).
    settled  — the deflection once the cue re-establishes a natural roll.
    """
    table = Table()
    R = BALL_RADIUS_M
    theta = math.radians(cut_angle_deg)

    original_dir = np.array([0.0, 1.0])

    # Cue at the contact instant, moving +y with a natural roll (ω_x = -v/R).
    cue = Ball(
        id="cue",
        position=np.array([0.0, 0.0]),
        velocity=original_dir * speed,
        angular_velocity=np.array([-speed / R, 0.0, 0.0]),
    )

    # Object ball positioned so the line of centers is at `theta` to the right
    # of the cue's path, and the balls are exactly in contact (|sep| = 2R).
    ob = Ball(
        id="1",
        position=np.array([2.0 * R * math.sin(theta), 2.0 * R * math.cos(theta)]),
    )

    cue2, _ob2 = ball_collision(cue, ob, table)
    immediate = _deg_between(cue2.velocity, original_dir)

    # Let the cue re-establish roll under cloth friction.
    dt = 0.001
    moving = cue2
    for _ in range(20000):
        if is_rolling(moving):
            break
        nxt = step_free_flight(moving, dt, table)
        if float(np.linalg.norm(nxt.velocity)) < 1e-4:
            break
        moving = nxt

    settled = _deg_between(moving.velocity, original_dir)
    return immediate, settled


class TestThirtyDegreeRule:
    def test_half_ball_hit_deflects_near_thirty(self) -> None:
        # Half-ball hit ≈ 30° cut angle.
        immediate, settled = _settled_deflection(30.0)
        # The rolling cue must settle near 30° — well short of the stun tangent.
        assert 25.0 <= settled <= 38.0, f"settled deflection {settled:.1f}° off 30° rule"

    def test_roll_pulls_in_from_the_stun_tangent(self) -> None:
        # Topspin should bend the cue forward: the settled deflection is
        # markedly smaller than the immediate post-collision tangent deflection.
        immediate, settled = _settled_deflection(30.0)
        assert settled < immediate - 10.0

    def test_rule_holds_across_a_range_of_cuts(self) -> None:
        # The hallmark of the 30° rule: the deflection stays near ~30° across a
        # band of cut angles, not just one.
        for cut in (22.0, 30.0, 40.0):
            _immediate, settled = _settled_deflection(cut)
            assert 22.0 <= settled <= 40.0, (
                f"cut {cut}° → settled {settled:.1f}°, outside the 30° band"
            )
