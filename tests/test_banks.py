"""Tests for the multi-rail bank-shot solver."""
from __future__ import annotations

import numpy as np
import pytest

from poolsauce import (
    Ball,
    Intention,
    Table,
    TableState,
    compose_bank_plan,
    solve_bank_shot,
    validate_pillar_output,
)
from poolsauce.solver import ShotSolverError


def _bankable_state() -> TableState:
    # OB low on the table, cue above it — a direct pot into a top pocket would
    # need an impossible backward cut, but a bottom-rail bank works.
    return TableState(table=Table(), balls=[
        Ball(id="cue", position=np.array([0.9, 0.9])),
        Ball(id="1", position=np.array([0.4, 0.5])),
    ])


class TestBankSolver:
    def test_finds_one_rail_bank(self) -> None:
        bank = solve_bank_shot(_bankable_state(), "1", "top-left", 1)
        assert bank.num_rails == 1
        assert len(bank.rail_sequence) == 1
        # Path: start at OB, one rail contact, then the pocket.
        assert len(bank.ob_path_points_m) == 3
        start = bank.ob_path_points_m[0]
        assert start == pytest.approx((0.4, 0.5), abs=1e-6)

    def test_verified_path_ends_at_pocket(self) -> None:
        bank = solve_bank_shot(_bankable_state(), "1", "top-left", 1)
        end = bank.ob_path_points_m[-1]
        pocket = Table().pockets["top-left"]
        assert end == pytest.approx((pocket[0], pocket[1]), abs=1e-6)

    def test_impossible_bank_raises(self) -> None:
        # A ball frozen on the cushion with no room can't make a 3-rail bank
        # into an adjacent pocket; the solver must refuse, not invent one.
        state = TableState(table=Table(), balls=[
            Ball(id="cue", position=np.array([0.6, 0.1])),
            Ball(id="1", position=np.array([0.05, 0.05])),
        ])
        with pytest.raises(ShotSolverError):
            solve_bank_shot(state, "1", "top-right", 3)


class TestBankPlan:
    def test_bank_plan_is_schema_valid(self) -> None:
        plan = compose_bank_plan(
            _bankable_state(),
            "bank-shot",
            Intention(target_ball_id="1", pocket="top-left", destination_descriptor="bank"),
            1,
        )
        validate_pillar_output(plan)  # raises if invalid

    def test_bank_plan_carries_path(self) -> None:
        plan = compose_bank_plan(
            _bankable_state(),
            "bank-shot",
            Intention(target_ball_id="1", pocket="top-left", destination_descriptor="bank"),
            1,
        )
        bank = plan["pillar_II"]["bank"]
        assert bank["num_rails"] == 1
        assert len(bank["ob_path_points_m"]) >= 3
        assert plan["pillar_II"]["rails_involved"] == list(bank["rail_sequence"])
