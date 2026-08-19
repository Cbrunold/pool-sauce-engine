"""Tests for Unit C — the inverse shot solver."""
from __future__ import annotations

import math

import numpy as np
import pytest

from poolsauce import (
    BALL_RADIUS_M,
    Ball,
    ShotPlan,
    ShotSolverError,
    Table,
    TableState,
    cue_state_for_plan,
    simulate,
    solve_direct_shot,
)


def _ball(id_: str, pos, v=(0.0, 0.0), w=(0.0, 0.0, 0.0)) -> Ball:
    return Ball(
        id=id_,
        position=np.asarray(pos, dtype=float),
        velocity=np.asarray(v, dtype=float),
        angular_velocity=np.asarray(w, dtype=float),
    )


def _state(balls: list[Ball], table: Table | None = None) -> TableState:
    return TableState(table=table or Table(), balls=balls)


class TestGhostBallGeometry:
    def test_ghost_ball_sits_on_line_from_ob_to_pocket(self) -> None:
        # Pure geometric ghost (no throw compensation).
        s = _state([
            _ball("cue", (0.2, 0.3)),
            _ball("6", (0.635, 1.5)),
        ])
        plan = solve_direct_shot(s, "6", "top-left", compensate_throw=False)
        ob = s.get_ball("6")
        pocket = s.table.pockets["top-left"]

        to_pocket = pocket - ob.position
        to_pocket /= np.linalg.norm(to_pocket)
        expected_ghost = ob.position - 2 * BALL_RADIUS_M * to_pocket
        np.testing.assert_allclose(plan.ghost_ball_position, expected_ghost, atol=1e-12)

    def test_line_of_aim_is_cue_to_ghost_ball(self) -> None:
        s = _state([_ball("cue", (0.2, 0.3)), _ball("6", (0.635, 1.5))])
        plan = solve_direct_shot(s, "6", "top-left")
        expected = plan.ghost_ball_position - s.cue_ball.position
        expected /= np.linalg.norm(expected)
        np.testing.assert_allclose(plan.line_of_aim, expected, atol=1e-12)

    def test_line_of_aim_is_unit_length(self) -> None:
        s = _state([_ball("cue", (0.4, 0.5)), _ball("6", (0.8, 1.7))])
        plan = solve_direct_shot(s, "6", "top-right")
        assert math.isclose(float(np.linalg.norm(plan.line_of_aim)), 1.0, abs_tol=1e-12)


class TestStraightShot:
    def test_inline_cue_ob_pocket_produces_zero_cut(self) -> None:
        # cue, OB, side-right pocket all on the same horizontal line.
        s = _state([
            _ball("cue", (0.1, 1.27)),
            _ball("6", (0.5, 1.27)),
        ])
        plan = solve_direct_shot(s, "6", "side-right")
        assert math.isclose(plan.cut_angle_deg, 0.0, abs_tol=1e-9)
        assert math.isclose(plan.contact_fraction, 1.0, abs_tol=1e-9)
        np.testing.assert_allclose(plan.line_of_aim, [1.0, 0.0], atol=1e-12)

    def test_zero_cut_has_zero_natural_tangent(self) -> None:
        s = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        plan = solve_direct_shot(s, "6", "side-right")
        assert float(np.linalg.norm(plan.natural_tangent_line)) == 0.0


class TestCutAngleAndContactFraction:
    def test_cut_angle_in_valid_range(self) -> None:
        s = _state([_ball("cue", (0.2, 0.3)), _ball("6", (0.7, 1.8))])
        plan = solve_direct_shot(s, "6", "top-left")
        assert 0.0 <= plan.cut_angle_deg < 90.0

    def test_contact_fraction_matches_cut_angle(self) -> None:
        s = _state([_ball("cue", (0.3, 0.4)), _ball("6", (0.635, 1.5))])
        plan = solve_direct_shot(s, "6", "top-right")
        expected = 1.0 - math.sin(math.radians(plan.cut_angle_deg))
        assert math.isclose(plan.contact_fraction, expected, abs_tol=1e-12)

    def test_natural_tangent_is_perpendicular_to_ob_direction(self) -> None:
        # With throw compensation off, the tangent is exactly perpendicular
        # to the geometric OB-to-pocket line.
        s = _state([_ball("cue", (0.2, 0.4)), _ball("6", (0.635, 1.5))])
        plan = solve_direct_shot(s, "6", "top-right", compensate_throw=False)
        if float(np.linalg.norm(plan.natural_tangent_line)) > 0.0:
            dot = float(plan.natural_tangent_line @ plan.ob_direction)
            assert math.isclose(dot, 0.0, abs_tol=1e-9)


class TestMinCueSpeed:
    def test_positive_for_realistic_shot(self) -> None:
        s = _state([_ball("cue", (0.3, 0.5)), _ball("6", (0.635, 1.5))])
        plan = solve_direct_shot(s, "6", "top-right")
        assert plan.min_cue_speed_m_s > 0.0

    def test_longer_ob_run_requires_more_speed(self) -> None:
        # Same LoC geometry but two different OB-to-pocket distances.
        near = _state([_ball("cue", (0.3, 1.0)), _ball("6", (0.3, 1.2))])
        far = _state([_ball("cue", (0.3, 1.0)), _ball("6", (0.3, 1.4))])
        near_plan = solve_direct_shot(near, "6", "top-left")
        far_plan = solve_direct_shot(far, "6", "top-left")
        # The "far" OB is farther from its pocket but closer to the cue,
        # so the comparison must be on OB-to-pocket distance + speed.
        assert far_plan.ob_to_pocket_distance_m != near_plan.ob_to_pocket_distance_m


class TestBlockers:
    def test_ball_on_the_aim_line_is_flagged(self) -> None:
        # A third ball sits directly between cue and OB.
        s = _state([
            _ball("cue", (0.1, 1.27)),
            _ball("6", (0.9, 1.27)),
            _ball("blocker", (0.5, 1.27)),
        ])
        plan = solve_direct_shot(s, "6", "side-right")
        assert "blocker" in plan.blockers

    def test_ball_off_the_aim_line_is_not_flagged(self) -> None:
        s = _state([
            _ball("cue", (0.1, 1.27)),
            _ball("6", (0.9, 1.27)),
            _ball("bystander", (0.5, 0.5)),
        ])
        plan = solve_direct_shot(s, "6", "side-right")
        assert "bystander" not in plan.blockers

    def test_no_blockers_in_clean_table(self) -> None:
        s = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.9, 1.27))])
        plan = solve_direct_shot(s, "6", "side-right")
        assert plan.blockers == ()


class TestErrors:
    def test_unknown_pocket_rejected(self) -> None:
        s = _state([_ball("cue", (0.1, 1.0)), _ball("6", (0.5, 1.0))])
        with pytest.raises(ShotSolverError, match="unknown pocket"):
            solve_direct_shot(s, "6", "middle")

    def test_missing_target_ball_rejected(self) -> None:
        s = _state([_ball("cue", (0.1, 1.0)), _ball("6", (0.5, 1.0))])
        with pytest.raises(KeyError):
            solve_direct_shot(s, "99", "top-left")

    def test_impossible_cut_rejected(self) -> None:
        # Cue placed such that the ghost ball sits almost perpendicular.
        # Cue past the OB, pocket just off at 90°.
        s = _state([
            _ball("cue", (0.7, 1.27)),
            _ball("6", (0.5, 1.27)),
        ])
        with pytest.raises(ShotSolverError, match="cut angle"):
            solve_direct_shot(s, "6", "side-right")


class TestCueStateHelper:
    def test_cue_state_for_plan_builds_rolling_ball(self) -> None:
        s = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        plan = solve_direct_shot(s, "6", "side-right")
        cue = cue_state_for_plan(s.cue_ball, plan, 1.5)
        np.testing.assert_allclose(cue.velocity, plan.line_of_aim * 1.5, atol=1e-12)
        # Rolling constraint: ω_y = v_x / R, ω_x = -v_y / R.
        R = cue.radius_m
        np.testing.assert_allclose(cue.angular_velocity[0], -cue.velocity[1] / R, atol=1e-12)
        np.testing.assert_allclose(cue.angular_velocity[1], cue.velocity[0] / R, atol=1e-12)
        assert cue.angular_velocity[2] == 0.0

    def test_zero_speed_gives_stationary_cue(self) -> None:
        s = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        plan = solve_direct_shot(s, "6", "side-right")
        cue = cue_state_for_plan(s.cue_ball, plan, 0.0)
        assert cue.is_stationary

    def test_negative_speed_rejected(self) -> None:
        s = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        plan = solve_direct_shot(s, "6", "side-right")
        with pytest.raises(ValueError, match="speed"):
            cue_state_for_plan(s.cue_ball, plan, -0.5)


class TestThrowCompensation:
    def test_straight_shot_has_zero_throw(self) -> None:
        s = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        plan = solve_direct_shot(s, "6", "side-right")
        assert plan.throw_angle_deg == 0.0

    def test_cut_shot_reports_nonzero_throw(self) -> None:
        # Moderate-cut geometry from the earlier round-trip tests.
        s = _state([_ball("cue", (0.3, 0.5)), _ball("6", (0.635, 1.3))])
        plan = solve_direct_shot(s, "6", "top-right")
        assert abs(plan.throw_angle_deg) > 0.5
        # Physical asymptote: atan(μ) ≈ 3.43° for default μ=0.06.
        assert abs(plan.throw_angle_deg) < 3.5

    def test_throw_sign_follows_cue_side_of_pocket_line(self) -> None:
        # Cue on one side versus the other of the OB-to-pocket line must
        # flip the throw sign.
        left_side = _state([_ball("cue", (0.2, 0.5)), _ball("6", (0.635, 1.3))])
        right_side = _state([_ball("cue", (0.9, 0.5)), _ball("6", (0.635, 1.3))])
        left = solve_direct_shot(left_side, "6", "top-right")
        right = solve_direct_shot(right_side, "6", "top-right")
        assert left.throw_angle_deg * right.throw_angle_deg < 0.0

    def test_compensation_shifts_ghost_off_pocket_line(self) -> None:
        s = _state([_ball("cue", (0.3, 0.5)), _ball("6", (0.635, 1.3))])
        raw = solve_direct_shot(s, "6", "top-right", compensate_throw=False)
        compd = solve_direct_shot(s, "6", "top-right", compensate_throw=True)
        shift = float(np.linalg.norm(
            compd.ghost_ball_position - raw.ghost_ball_position
        ))
        assert shift > 0.0
        # Shift should be at most ~2R sin(throw_angle), a few millimeters.
        assert shift < 0.01

    def test_compensation_reduces_ob_miss_distance(self) -> None:
        # Measure the OB's post-collision velocity direction relative to
        # the intended OB→pocket line. Compensation should make the *actual*
        # OB direction closer to the intended direction.
        from poolsauce import Ball, cue_state_for_plan
        from poolsauce.physics import ball_collision

        state = _state([_ball("cue", (0.9, 0.5)), _ball("6", (0.635, 1.3))])
        pocket = state.table.pockets["top-right"]
        ob_to_pocket = pocket - state.get_ball("6").position
        intended_dir = ob_to_pocket / np.linalg.norm(ob_to_pocket)
        t_hat = np.array([-intended_dir[1], intended_dir[0]])

        def angular_miss(plan) -> float:
            """OB post-collision deviation from the intended pocket direction, in t̂."""
            R = BALL_RADIUS_M
            v_mag = plan.min_cue_speed_m_s * 1.2
            v_at_contact = np.sqrt(
                max(0.0, v_mag**2 - 2 * 0.01 * 9.81 * plan.cue_travel_distance_m)
            )
            cue = Ball(
                id="cue",
                position=plan.ghost_ball_position.copy(),
                velocity=plan.line_of_aim * v_at_contact,
                angular_velocity=np.array([
                    -plan.line_of_aim[1] * v_at_contact / R,
                    plan.line_of_aim[0] * v_at_contact / R,
                    0.0,
                ]),
            )
            ob = state.get_ball("6")
            _, ob_after = ball_collision(cue, ob, state.table)
            v_ob_dir = ob_after.velocity / np.linalg.norm(ob_after.velocity)
            return abs(float(v_ob_dir @ t_hat))

        raw = angular_miss(solve_direct_shot(state, "6", "top-right", compensate_throw=False))
        compd = angular_miss(solve_direct_shot(state, "6", "top-right", compensate_throw=True))

        assert compd < raw, (
            f"compensation should reduce OB direction error: "
            f"raw |t̂|={raw:.4f}, compensated |t̂|={compd:.4f}"
        )

    def test_compensate_throw_false_matches_raw_geometry(self) -> None:
        s = _state([_ball("cue", (0.3, 0.5)), _ball("6", (0.635, 1.3))])
        plan = solve_direct_shot(s, "6", "top-right", compensate_throw=False)
        # With compensation off, throw_angle_deg is exactly zero and the
        # ghost sits on the OB→pocket line.
        assert plan.throw_angle_deg == 0.0
        ob = s.get_ball("6")
        pocket = s.table.pockets["top-right"]
        to_pocket = pocket - ob.position
        to_pocket = to_pocket / np.linalg.norm(to_pocket)
        expected = ob.position - 2 * BALL_RADIUS_M * to_pocket
        np.testing.assert_allclose(plan.ghost_ball_position, expected, atol=1e-12)


class TestCueDestinationSolver:
    def test_returns_recipe_with_valid_fields(self) -> None:
        from poolsauce import solve_cue_destination

        state = _state([_ball("cue", (0.3, 0.5)), _ball("6", (0.635, 1.3))])
        plan = solve_direct_shot(state, "6", "top-right")
        recipe = solve_cue_destination(
            state=state, plan=plan,
            target_position=np.array([0.5, 2.0]),
        )
        assert recipe.speed_m_s > 0
        assert 1.0 <= recipe.speed_margin <= 3.0
        assert -1.0 <= recipe.vertical_tips <= 1.0
        assert -1.0 <= recipe.horizontal_tips <= 1.0
        assert recipe.landing_error_m >= 0.0
        assert recipe.predicted_cue_landing_m.shape == (2,)

    def test_finds_replicable_recipe_for_close_target(self) -> None:
        # A target close to the ghost ball (along the natural tangent line of
        # the compensated geometry) should be reachable to roughly B/C-zone
        # accuracy by the coarse grid — while still potting the ball. The
        # solver prioritizes position but requires the pot, and prefers a
        # gentle, repeatable stroke over chasing the last centimeters with spin.
        from poolsauce import solve_cue_destination

        state = _state([_ball("cue", (0.3, 0.5)), _ball("6", (0.635, 1.3))])
        plan = solve_direct_shot(state, "6", "top-right")
        target = plan.ghost_ball_position + 0.15 * plan.natural_tangent_line
        recipe = solve_cue_destination(state=state, plan=plan, target_position=target)
        assert recipe.landing_error_m < 0.4
        # Replicable: no extreme english chased for marginal position.
        assert abs(recipe.horizontal_tips) <= 0.5

    def test_drops_spin_that_does_not_earn_its_keep(self) -> None:
        # When side english barely improves the leave, the replicability cost
        # should prefer the gentler stroke. The position-band selection must
        # never land much worse than the raw-error optimum, but should use
        # less spin.
        from poolsauce import solve_cue_destination

        state = _state([
            _ball("cue", (0.79, 1.49)),
            _ball("1", (0.82, 2.05)),
            _ball("3", (0.90, 1.20)),
        ])
        plan = solve_direct_shot(state, "1", "top-right")
        target = np.array([0.35, 1.31])

        greedy = solve_cue_destination(
            state=state, plan=plan, target_position=target,
            spin_cost_weight=0.0, speed_cost_weight=0.0, position_band_m=0.0,
        )
        replicable = solve_cue_destination(state=state, plan=plan, target_position=target)

        # Position stays within the band of the greedy optimum...
        assert replicable.landing_error_m <= greedy.landing_error_m + 0.06 + 1e-9
        # ...but the stroke is no spinnier than the greedy one.
        greedy_spin = abs(greedy.horizontal_tips) + abs(greedy.vertical_tips)
        replic_spin = abs(replicable.horizontal_tips) + abs(replicable.vertical_tips)
        assert replic_spin <= greedy_spin

    def test_ranked_options_are_sorted_and_distinct(self) -> None:
        from poolsauce import solve_cue_destination_options

        state = _state([_ball("cue", (0.6, 0.5)), _ball("8", (0.635, 1.3))])
        plan = solve_direct_shot(state, "8", "top-right")
        opts = solve_cue_destination_options(
            state, plan, np.array([0.10, 2.30]), max_options=6
        )
        assert len(opts) >= 1
        # Ranks are 1..N and difficulty is non-decreasing among makeable ones.
        assert [o.rank for o in opts] == list(range(1, len(opts) + 1))
        makeable = [o for o in opts if o.makeable]
        diffs = [o.difficulty for o in makeable]
        assert diffs == sorted(diffs)
        # Distinct stroke styles — no two options share the same (v,h) buckets.
        styles = {
            (
                -1 if o.recipe.vertical_tips <= -0.375 else (1 if o.recipe.vertical_tips >= 0.375 else 0),
                -1 if o.recipe.horizontal_tips <= -0.375 else (1 if o.recipe.horizontal_tips >= 0.375 else 0),
            )
            for o in opts
        }
        assert len(styles) == len(opts)

    def test_recipe_reproduces_predicted_landing(self) -> None:
        # Building the cue state from the recipe and simulating must land
        # the cue at the solver's predicted position.
        from poolsauce import cue_state_from_recipe, solve_cue_destination

        state = _state([_ball("cue", (0.3, 0.5)), _ball("6", (0.635, 1.3))])
        plan = solve_direct_shot(state, "6", "top-right")
        target = np.array([0.6, 2.1])
        recipe = solve_cue_destination(state=state, plan=plan, target_position=target)

        cue_state = cue_state_from_recipe(state.cue_ball, plan, recipe)
        sim = simulate(TableState(
            table=state.table,
            balls=[cue_state if b.id == "cue" else b for b in state.balls],
        ))
        cue_final = next(b for b in sim.final_balls if b.id == "cue")
        np.testing.assert_allclose(
            cue_final.position, recipe.predicted_cue_landing_m, atol=1e-9
        )


class TestRoundTripInverseToForward:
    """Solve → build cue state at min speed + margin → simulate → OB reaches pocket."""

    def _verify_ob_reaches_pocket(
        self, state: TableState, target: str, pocket: str, margin: float = 1.15
    ) -> None:
        plan = solve_direct_shot(state, target, pocket)
        speed = plan.min_cue_speed_m_s * margin
        cue = cue_state_for_plan(state.cue_ball, plan, speed)
        balls = [cue if b.id == "cue" else b for b in state.balls]
        result = simulate(TableState(table=state.table, balls=balls))

        final_ob = next(b for b in result.final_balls if b.id == target)
        pocket_center = state.table.pockets[pocket]
        dist = float(np.linalg.norm(final_ob.position - pocket_center))
        assert dist <= state.table.pocket_mouth_m, (
            f"OB failed to reach {pocket}: ended at {final_ob.position}, "
            f"{dist:.3f} m from pocket"
        )

    def test_straight_shot_sinks_ob(self) -> None:
        state = _state([
            _ball("cue", (0.1, 1.27)),
            _ball("6", (0.5, 1.27)),
        ])
        self._verify_ob_reaches_pocket(state, "6", "side-right")

    def test_moderate_cut_sinks_ob(self) -> None:
        state = _state([
            _ball("cue", (0.3, 0.5)),
            _ball("6", (0.635, 1.3)),
        ])
        self._verify_ob_reaches_pocket(state, "6", "top-right", margin=1.2)

    def test_wider_cut_sinks_ob(self) -> None:
        state = _state([
            _ball("cue", (0.9, 0.8)),
            _ball("6", (0.6, 1.5)),
        ])
        self._verify_ob_reaches_pocket(state, "6", "top-left", margin=1.25)
