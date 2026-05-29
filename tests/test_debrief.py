"""Tests for Unit G — the Pillar V debrief composer."""
from __future__ import annotations

import numpy as np
import pytest

from poolsauce import (
    Ball,
    DebriefOverrides,
    Intention,
    SauceChoice,
    Table,
    TableState,
    compose_debrief,
    compose_pillar_plan,
    cue_state_for_plan,
    simulate,
    solve_direct_shot,
    validate_pillar_output,
)


def _ball(id_: str, pos) -> Ball:
    return Ball(id=id_, position=np.asarray(pos, dtype=float))


def _state(balls: list[Ball]) -> TableState:
    return TableState(table=Table(), balls=balls)


def _plan_and_sim(dest_coords=(0.5, 1.27)) -> tuple[dict, any]:
    state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
    plan = compose_pillar_plan(
        state=state,
        shot_id="debrief-test",
        intention=Intention(
            target_ball_id="6",
            pocket="side-right",
            destination_descriptor="center-table",
            destination_coordinates_m=dest_coords,
            destination_tolerance_m=0.1,
        ),
    )
    # Simulate the actual shot: solve + fire cue at min_speed * 1.15
    solve = solve_direct_shot(state, "6", "side-right")
    cue = cue_state_for_plan(state.cue_ball, solve, solve.min_cue_speed_m_s * 1.15)
    sim_state = TableState(table=state.table, balls=[cue, state.get_ball("6")])
    sim_result = simulate(sim_state)
    return plan, sim_result


class TestDebriefValidation:
    def test_validates_against_schema(self) -> None:
        plan, sim = _plan_and_sim()
        out = compose_debrief(plan, sim)
        validate_pillar_output(out)

    def test_plan_fields_preserved(self) -> None:
        plan, sim = _plan_and_sim()
        out = compose_debrief(plan, sim)
        assert out["shot_id"] == plan["shot_id"]
        assert out["pillar_I"] == plan["pillar_I"]
        assert out["pillar_II"] == plan["pillar_II"]
        assert out["pillar_III"] == plan["pillar_III"]

    def test_pillar_V_added(self) -> None:
        plan, sim = _plan_and_sim()
        out = compose_debrief(plan, sim)
        assert "pillar_V" in out
        p5 = out["pillar_V"]
        for field in (
            "zone_landing",
            "correct_side",
            "spin_review",
            "pace_control",
            "risk_zones_crossed",
            "mastery_one_percent",
        ):
            assert field in p5


class TestZoneInference:
    def test_actual_coords_and_miss_vector_reported(self) -> None:
        plan, sim = _plan_and_sim()
        out = compose_debrief(plan, sim)
        zl = out["pillar_V"]["zone_landing"]
        assert len(zl["actual_coordinates_m"]) == 2
        assert len(zl["miss_vector_m"]) == 2

    def test_landing_near_target_is_a_zone(self) -> None:
        plan, sim = _plan_and_sim()
        # Pick the destination to be near the cue's actual landing.
        actual = next(b.position for b in sim.final_balls if b.id == "cue")
        plan["pillar_I"]["destination"]["coordinates_m"] = [
            float(actual[0]), float(actual[1]),
        ]
        out = compose_debrief(plan, sim)
        assert out["pillar_V"]["zone_landing"]["zone"] == "A"
        assert out["pillar_V"]["pace_control"] == "clean"

    def test_landing_far_from_target_is_c_zone(self) -> None:
        plan, sim = _plan_and_sim(dest_coords=(0.0, 0.0))
        out = compose_debrief(plan, sim)
        assert out["pillar_V"]["zone_landing"]["zone"] == "C"


class TestOverrides:
    def test_subjective_fields_use_defaults(self) -> None:
        plan, sim = _plan_and_sim()
        out = compose_debrief(plan, sim)
        p5 = out["pillar_V"]
        assert p5["correct_side"] == "natural"
        assert p5["spin_review"]["verdict"] == "clean"
        assert p5["spin_review"]["notes"]  # non-empty
        assert p5["mastery_one_percent"]["excellent"]
        assert p5["mastery_one_percent"]["fragile"]

    def test_overrides_are_applied(self) -> None:
        plan, sim = _plan_and_sim()
        overrides = DebriefOverrides(
            spin_verdict="too much",
            spin_notes="Over-spun the cue; it drifted wide.",
            correct_side="high",
            pace_control="punchy",
            risk_zones_crossed=("scratch path",),
            mastery_excellent="Held the plane clean.",
            mastery_fragile="Trim the english by half.",
        )
        out = compose_debrief(plan, sim, overrides)
        p5 = out["pillar_V"]
        assert p5["spin_review"]["verdict"] == "too much"
        assert p5["spin_review"]["notes"] == "Over-spun the cue; it drifted wide."
        assert p5["correct_side"] == "high"
        assert p5["pace_control"] == "punchy"
        assert p5["risk_zones_crossed"] == ["scratch path"]
        assert p5["mastery_one_percent"]["excellent"] == "Held the plane clean."
        assert p5["mastery_one_percent"]["fragile"] == "Trim the english by half."

    def test_invalid_spin_verdict_rejected(self) -> None:
        plan, sim = _plan_and_sim()
        with pytest.raises(ValueError, match="spin_verdict"):
            compose_debrief(plan, sim, DebriefOverrides(spin_verdict="cosmic"))

    def test_invalid_correct_side_rejected(self) -> None:
        plan, sim = _plan_and_sim()
        with pytest.raises(ValueError, match="correct_side"):
            compose_debrief(plan, sim, DebriefOverrides(correct_side="sideways"))

    def test_invalid_risk_zone_rejected(self) -> None:
        plan, sim = _plan_and_sim()
        with pytest.raises(ValueError, match="risk zone"):
            compose_debrief(
                plan, sim,
                DebriefOverrides(risk_zones_crossed=("bad juju",)),
            )


class TestErrors:
    def test_plan_without_destination_coords_errors(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        plan = compose_pillar_plan(
            state=state,
            shot_id="nodest",
            intention=Intention(
                target_ball_id="6",
                pocket="side-right",
                destination_descriptor="somewhere vague",
                # no coordinates
            ),
        )
        _, sim = _plan_and_sim()
        with pytest.raises(KeyError, match="destination"):
            compose_debrief(plan, sim)

    def test_missing_cue_in_sim_errors(self) -> None:
        plan, _ = _plan_and_sim()
        # Simulate a board with no cue ball at all.
        state = _state([_ball("6", (0.5, 1.27))])
        sim = simulate(state)
        with pytest.raises(KeyError, match="cue"):
            compose_debrief(plan, sim)
