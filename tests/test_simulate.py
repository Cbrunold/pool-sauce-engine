"""Tests for Unit B.4 — the event loop (`simulate`)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from poolsauce import (
    BALL_RADIUS_M,
    Ball,
    SimEvent,
    SimulationResult,
    Table,
    TableState,
    simulate,
)


def _state(balls: list[Ball], table: Table | None = None) -> TableState:
    return TableState(table=table or Table(), balls=balls)


def _ball(id_: str, pos, v=(0.0, 0.0), w=(0.0, 0.0, 0.0)) -> Ball:
    return Ball(
        id=id_,
        position=np.asarray(pos, dtype=float),
        velocity=np.asarray(v, dtype=float),
        angular_velocity=np.asarray(w, dtype=float),
    )


class TestEmptyAndStillLife:
    def test_all_stationary_returns_immediately(self) -> None:
        s = _state([_ball("cue", (0.5, 0.5)), _ball("6", (0.7, 1.5))])
        out = simulate(s)
        assert out.events == ()
        assert out.total_time == 0.0
        np.testing.assert_array_equal(out.final_balls[0].position, [0.5, 0.5])
        np.testing.assert_array_equal(out.final_balls[1].position, [0.7, 1.5])

    def test_does_not_mutate_input_balls(self) -> None:
        ball = _ball("cue", (0.5, 0.5), v=(0.0, 1.0))
        s = _state([ball])
        v0 = ball.velocity.copy()
        _ = simulate(s)
        np.testing.assert_array_equal(ball.velocity, v0)


class TestSingleBallDynamics:
    def test_ball_rolls_to_rest_without_events(self) -> None:
        # Slow enough that the ball stops before reaching the top rail.
        v0 = 0.3
        R = BALL_RADIUS_M
        b = _ball("cue", (0.635, 1.0), v=(0.0, v0), w=(-v0 / R, 0.0, 0.0))
        out = simulate(_state([b]))
        assert out.events == ()
        t = Table()
        dy = v0 * v0 / (2 * t.cloth_rolling_friction * 9.81)
        np.testing.assert_allclose(out.final_balls[0].position, [0.635, 1.0 + dy], atol=1e-9)
        np.testing.assert_allclose(out.final_balls[0].velocity, [0.0, 0.0], atol=1e-10)

    def test_ball_bounces_off_top_rail(self) -> None:
        # Ball moving fast toward top rail — first event must be that rail.
        R = BALL_RADIUS_M
        b = _ball("cue", (0.5, 2.0), v=(0.0, 3.0), w=(-3.0 / R, 0.0, 0.0))
        out = simulate(_state([b]))
        assert len(out.events) >= 1
        first = out.events[0]
        assert first.kind == "cushion"
        assert first.detail == "top"
        assert first.ball_ids == ("cue",)
        np.testing.assert_allclose(out.final_balls[0].velocity, [0.0, 0.0], atol=1e-9)

    def test_multi_rail_bank_produces_ordered_events(self) -> None:
        # Ball moving diagonally fast enough to ricochet off adjacent rails.
        R = BALL_RADIUS_M
        b = _ball("cue", (0.2, 1.27), v=(4.0, 4.0), w=(-4.0 / R, 4.0 / R, 0.0))
        out = simulate(_state([b]))
        times = [e.time for e in out.events]
        assert times == sorted(times)
        assert all(e.kind == "cushion" for e in out.events)
        assert len(out.events) >= 2


class TestBallCollision:
    def test_head_on_collision_pockets_momentum_forward(self) -> None:
        # Cue rolling toward OB straight above it. After collision, cue
        # should stop (e=0.92 leaves a small forward drift), OB should move
        # in +y and rest before the top rail if distances work out.
        R = BALL_RADIUS_M
        cue = _ball("cue", (0.5, 1.0), v=(0.0, 1.0), w=(-1.0 / R, 0.0, 0.0))
        ob = _ball("6", (0.5, 1.8))
        out = simulate(_state([cue, ob]))

        collisions = [e for e in out.events if e.kind == "collision"]
        assert len(collisions) >= 1
        assert set(collisions[0].ball_ids) == {"cue", "6"}

        # After everything settles, OB has advanced past its starting y.
        final_ob = next(b for b in out.final_balls if b.id == "6")
        assert final_ob.position[1] > 1.8
        # Cue is either roughly where it was, or slightly past, but OB leads.
        final_cue = next(b for b in out.final_balls if b.id == "cue")
        assert final_cue.position[1] < final_ob.position[1]

    def test_cut_shot_throws_object_ball_off_line(self) -> None:
        # Cue fired up the +y axis; OB offset in +x by half a ball radius,
        # producing a moderate cut at contact.
        R = BALL_RADIUS_M
        cue = _ball("cue", (0.5, 0.5), v=(0.0, 2.0), w=(-2.0 / R, 0.0, 0.0))
        ob = _ball("6", (0.5 + 0.5 * R, 1.0))
        out = simulate(_state([cue, ob]))
        collisions = [e for e in out.events if e.kind == "collision"]
        assert len(collisions) >= 1
        final_ob = next(b for b in out.final_balls if b.id == "6")
        # OB ends up off its starting point — cut deflects it away from +y axis.
        assert final_ob.position[0] > 0.5 + 0.5 * R  # thrown further in +x
        assert final_ob.position[1] > 1.0  # and forward


class TestConservationAcrossShots:
    def test_energy_never_exceeds_initial(self) -> None:
        R = BALL_RADIUS_M
        cue = _ball("cue", (0.5, 0.5), v=(0.2, 1.2), w=(-1.2 / R, 0.2 / R, 5.0))
        ob = _ball("6", (0.5, 1.3))
        s = _state([cue, ob])

        def ke(balls):
            total = 0.0
            for b in balls:
                lin = 0.5 * b.mass_kg * float(b.velocity @ b.velocity)
                I = 0.4 * b.mass_kg * b.radius_m * b.radius_m
                rot = 0.5 * I * float(b.angular_velocity @ b.angular_velocity)
                total += lin + rot
            return total

        ke_before = ke(s.balls)
        out = simulate(s)
        ke_after = ke(out.final_balls)
        assert ke_after <= ke_before + 1e-9

    def test_final_state_is_all_at_rest(self) -> None:
        R = BALL_RADIUS_M
        cue = _ball("cue", (0.3, 0.3), v=(2.0, 3.0), w=(-3.0 / R, 2.0 / R, 10.0))
        ob1 = _ball("6", (0.7, 1.2))
        ob2 = _ball("7", (0.4, 1.8))
        out = simulate(_state([cue, ob1, ob2]), max_time=120.0)
        for b in out.final_balls:
            assert b.is_stationary, f"{b.id} not at rest: v={b.velocity} w={b.angular_velocity}"


class TestEventLog:
    def test_event_times_strictly_increasing(self) -> None:
        R = BALL_RADIUS_M
        cue = _ball("cue", (0.2, 0.3), v=(3.0, 4.0), w=(-4.0 / R, 3.0 / R, 0.0))
        out = simulate(_state([cue]))
        times = [e.time for e in out.events]
        for a, b in zip(times, times[1:]):
            assert b > a

    def test_total_time_bounds_events(self) -> None:
        R = BALL_RADIUS_M
        cue = _ball("cue", (0.2, 0.3), v=(3.0, 4.0), w=(-4.0 / R, 3.0 / R, 0.0))
        out = simulate(_state([cue]))
        for e in out.events:
            assert 0.0 <= e.time <= out.total_time + 1e-9

    def test_cushion_event_has_one_ball_and_rail_detail(self) -> None:
        R = BALL_RADIUS_M
        cue = _ball("cue", (0.5, 2.0), v=(0.0, 3.0), w=(-3.0 / R, 0.0, 0.0))
        out = simulate(_state([cue]))
        cushion = [e for e in out.events if e.kind == "cushion"]
        assert cushion
        assert all(len(e.ball_ids) == 1 for e in cushion)
        assert all(e.detail in {"bottom", "top", "left", "right"} for e in cushion)

    def test_collision_event_has_two_balls_and_no_detail(self) -> None:
        R = BALL_RADIUS_M
        cue = _ball("cue", (0.5, 1.0), v=(0.0, 1.0), w=(-1.0 / R, 0.0, 0.0))
        ob = _ball("6", (0.5, 1.8))
        out = simulate(_state([cue, ob]))
        coll = [e for e in out.events if e.kind == "collision"]
        assert coll
        assert all(len(e.ball_ids) == 2 for e in coll)
        assert all(e.detail is None for e in coll)


class TestSimulationResultShape:
    def test_returns_simulation_result(self) -> None:
        out = simulate(_state([_ball("cue", (0.5, 0.5))]))
        assert isinstance(out, SimulationResult)
        assert isinstance(out.events, tuple)

    def test_events_are_simevent_instances(self) -> None:
        R = BALL_RADIUS_M
        b = _ball("cue", (0.5, 2.0), v=(0.0, 3.0), w=(-3.0 / R, 0.0, 0.0))
        out = simulate(_state([b]))
        for e in out.events:
            assert isinstance(e, SimEvent)


class TestPocketing:
    def test_ball_rolled_into_corner_pocket(self) -> None:
        R = BALL_RADIUS_M
        # Ball rolling straight at the top-right corner pocket.
        table = Table()
        pocket = table.pockets["top-right"]
        start = pocket - np.array([0.5, 0.5])
        direction = (pocket - start) / np.linalg.norm(pocket - start)
        v0 = 2.5
        v = direction * v0
        b = _ball("cue", start, v=tuple(v), w=tuple((-v[1] / R, v[0] / R, 0.0)))
        out = simulate(_state([b], table=table))
        assert "cue" in out.pocketed
        pocket_events = [e for e in out.events if e.kind == "pocket"]
        assert len(pocket_events) == 1
        assert pocket_events[0].detail == "top-right"
        assert pocket_events[0].ball_ids == ("cue",)
        np.testing.assert_allclose(out.final_balls[0].position, pocket, atol=1e-12)

    def test_pocketed_ball_stays_at_rest_in_pocket(self) -> None:
        R = BALL_RADIUS_M
        table = Table()
        pocket = table.pockets["bottom-left"]
        start = pocket + np.array([0.3, 0.3])
        direction = -(start - pocket) / np.linalg.norm(start - pocket)
        v = direction * 2.0
        b = _ball("cue", start, v=tuple(v), w=tuple((-v[1] / R, v[0] / R, 0.0)))
        out = simulate(_state([b], table=table))
        final = out.final_balls[0]
        np.testing.assert_array_equal(final.velocity, [0.0, 0.0])
        np.testing.assert_array_equal(final.angular_velocity, [0.0, 0.0, 0.0])

    def test_ball_missing_pocket_still_bounces_off_nearby_cushion(self) -> None:
        R = BALL_RADIUS_M
        # Aim well away from any pocket.
        b = _ball("cue", (0.5, 2.0), v=(0.0, 2.0), w=(-2.0 / R, 0.0, 0.0))
        out = simulate(_state([b]))
        assert out.pocketed == ()
        cushion_events = [e for e in out.events if e.kind == "cushion"]
        assert cushion_events  # hit the top rail cleanly


class TestBallsAreIndependentWhenFarApart:
    def test_non_interacting_balls_evolve_independently(self) -> None:
        R = BALL_RADIUS_M
        # Ball A at bottom-left heading nowhere useful; ball B at top-right.
        a = _ball("a", (0.3, 0.5), v=(0.0, 0.5), w=(-0.5 / R, 0.0, 0.0))
        b = _ball("b", (1.0, 2.0), v=(0.0, -0.5), w=(0.5 / R, 0.0, 0.0))
        out = simulate(_state([a, b]))
        # Expect zero collision events; they may each rest cleanly.
        assert not any(e.kind == "collision" for e in out.events)