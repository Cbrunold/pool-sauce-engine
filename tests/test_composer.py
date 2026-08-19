"""Tests for Unit F — the Pillar I-III composer."""
from __future__ import annotations

import numpy as np
import pytest

from poolsauce import (
    Ball,
    Intention,
    SauceChoice,
    ShotSolverError,
    Table,
    TableState,
    compose_pillar_plan,
    validate_pillar_output,
)


def _ball(id_: str, pos) -> Ball:
    return Ball(id=id_, position=np.asarray(pos, dtype=float))


def _state(balls: list[Ball]) -> TableState:
    return TableState(table=Table(), balls=balls)


class TestCompose:
    def test_straight_shot_validates_against_schema(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        out = compose_pillar_plan(
            state=state,
            shot_id="test-straight-side-right",
            intention=Intention(
                target_ball_id="6",
                pocket="side-right",
                destination_descriptor="center-table for the 7",
            ),
        )
        validate_pillar_output(out)  # raises on failure

    def test_cut_shot_validates(self) -> None:
        state = _state([_ball("cue", (0.3, 0.5)), _ball("6", (0.635, 1.3))])
        out = compose_pillar_plan(
            state=state,
            shot_id="test-cut-top-right",
            intention=Intention(
                target_ball_id="6",
                pocket="top-right",
                destination_descriptor="high side of the 7",
                destination_coordinates_m=(0.5, 1.0),
                destination_tolerance_m=0.12,
            ),
            sauce=SauceChoice(
                stroke="zest of follow",
                english="pinch of right",
                force="measured dose",
                acceleration="controlled",
            ),
        )
        validate_pillar_output(out)

    def test_shot_id_propagated(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        out = compose_pillar_plan(
            state=state,
            shot_id="abc-123",
            intention=Intention(
                target_ball_id="6",
                pocket="side-right",
                destination_descriptor="anywhere",
            ),
        )
        assert out["shot_id"] == "abc-123"

    def test_pillar_I_carries_intention(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        out = compose_pillar_plan(
            state=state,
            shot_id="intent-check",
            intention=Intention(
                target_ball_id="6",
                pocket="side-right",
                destination_descriptor="for the 7",
                destination_coordinates_m=(0.4, 1.0),
                destination_tolerance_m=0.15,
            ),
        )
        p1 = out["pillar_I"]
        assert p1["target"] == "6"
        assert p1["pocket"] == "side-right"
        assert p1["destination"]["descriptor"] == "for the 7"
        assert p1["destination"]["coordinates_m"] == [0.4, 1.0]
        assert p1["destination"]["tolerance_m"] == 0.15
        assert p1["intention_pure"] is True

    def test_pillar_II_contains_line_of_aim_from_cue(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        out = compose_pillar_plan(
            state=state,
            shot_id="loa-check",
            intention=Intention(
                target_ball_id="6", pocket="side-right",
                destination_descriptor="x",
            ),
        )
        vec = out["pillar_II"]["line_of_aim"]["vector"]
        assert len(vec) == 4
        assert vec[0] == 0.1
        assert vec[1] == 1.27
        # Ghost ball is between cue and OB along +x.
        assert vec[2] > 0.1
        assert vec[2] < 0.5

    def test_pillar_II_contact_reports_straight_as_center_ball(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        out = compose_pillar_plan(
            state=state,
            shot_id="center",
            intention=Intention(
                target_ball_id="6", pocket="side-right",
                destination_descriptor="x",
            ),
        )
        cp = out["pillar_II"]["contact_point"]
        assert cp["cut_angle_deg"] < 1.0
        assert cp["ball_fraction"] > 0.99
        assert "full" in cp["description"].lower() or "center" in cp["description"].lower()

    def test_pillar_III_english_matches_sauce_input(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        out = compose_pillar_plan(
            state=state,
            shot_id="english-test",
            intention=Intention(
                target_ball_id="6", pocket="side-right",
                destination_descriptor="x",
            ),
            sauce=SauceChoice(english="drop of right"),
        )
        p3 = out["pillar_III"]
        assert p3["english"]["sauce_term"] == "drop of right"
        assert p3["english"]["tips_offset"] == 0.50

    def test_stroke_type_mapping(self) -> None:
        cases = [
            ("spoon of stun", "stun"),
            ("zest of follow", "stun-follow"),
            ("full follow", "follow"),
            ("whisper of draw", "stun-draw"),
            ("full draw", "draw"),
        ]
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        for stroke_phrase, expected_type in cases:
            out = compose_pillar_plan(
                state=state,
                shot_id=f"stroke-{expected_type}",
                intention=Intention(
                    target_ball_id="6", pocket="side-right",
                    destination_descriptor="x",
                ),
                sauce=SauceChoice(stroke=stroke_phrase),
            )
            assert out["pillar_III"]["stroke"]["type"] == expected_type
            assert out["pillar_III"]["stroke"]["sauce_term"] == stroke_phrase

    def test_pillar_IV_is_user_owned(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        out = compose_pillar_plan(
            state=state, shot_id="pillar4",
            intention=Intention(
                target_ball_id="6", pocket="side-right",
                destination_descriptor="x",
            ),
        )
        assert out["pillar_IV"]["owned_by_user"] is True

    def test_rails_involved_defaults_to_none(self) -> None:
        # Direct shot with no rails touched by cue.
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        out = compose_pillar_plan(
            state=state, shot_id="norails",
            intention=Intention(
                target_ball_id="6", pocket="side-right",
                destination_descriptor="x",
            ),
        )
        assert out["pillar_II"]["rails_involved"] == ["none"]

    def test_doctrine_line_optional(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        out = compose_pillar_plan(
            state=state, shot_id="doctrine",
            intention=Intention(
                target_ball_id="6", pocket="side-right",
                destination_descriptor="x",
            ),
            doctrine_line="The samurai does not hope to make the shot — he makes it.",
        )
        assert "doctrine_line" in out
        validate_pillar_output(out)

    def test_invalid_force_rejected(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        with pytest.raises(ValueError, match="force"):
            compose_pillar_plan(
                state=state, shot_id="bad",
                intention=Intention(
                    target_ball_id="6", pocket="side-right",
                    destination_descriptor="x",
                ),
                sauce=SauceChoice(force="crushing"),
            )

    def test_invalid_acceleration_rejected(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        with pytest.raises(ValueError, match="acceleration"):
            compose_pillar_plan(
                state=state, shot_id="bad",
                intention=Intention(
                    target_ball_id="6", pocket="side-right",
                    destination_descriptor="x",
                ),
                sauce=SauceChoice(acceleration="mystical"),
            )

    def test_solver_error_propagates(self) -> None:
        state = _state([_ball("cue", (0.8, 1.27)), _ball("6", (0.5, 1.27))])
        with pytest.raises(ShotSolverError):
            compose_pillar_plan(
                state=state, shot_id="impossible",
                intention=Intention(
                    target_ball_id="6", pocket="side-right",
                    destination_descriptor="x",
                ),
            )

    def test_custom_recipe_rationale_used(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        out = compose_pillar_plan(
            state=state, shot_id="rationale",
            intention=Intention(
                target_ball_id="6", pocket="side-right",
                destination_descriptor="x",
            ),
            sauce=SauceChoice(recipe_rationale="Because the table demands it."),
        )
        assert out["pillar_III"]["recipe_rationale"] == "Because the table demands it."

    def test_table_state_included(self) -> None:
        state = _state([_ball("cue", (0.1, 1.27)), _ball("6", (0.5, 1.27))])
        out = compose_pillar_plan(
            state=state, shot_id="tablestate",
            intention=Intention(
                target_ball_id="6", pocket="side-right",
                destination_descriptor="x",
            ),
        )
        ts = out["table_state"]
        assert ts["cue_ball"] == {"x_m": 0.1, "y_m": 1.27}
        ids = {b["id"] for b in ts["balls"]}
        assert ids == {"cue", "6"}
        target_entry = next(b for b in ts["balls"] if b["id"] == "6")
        assert target_entry["is_target"] is True
