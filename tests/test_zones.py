"""Tests for Unit E — the zone evaluator."""
from __future__ import annotations

import numpy as np
import pytest

from poolsauce import (
    Ball,
    Table,
    TableState,
    ZoneClassification,
    classify_zone_by_distance,
    classify_zone_for_next_shot,
)


def _ball(id_: str, pos) -> Ball:
    return Ball(id=id_, position=np.asarray(pos, dtype=float))


def _state(balls: list[Ball]) -> TableState:
    return TableState(table=Table(), balls=balls)


class TestDistanceBased:
    def test_inside_a_radius_is_a(self) -> None:
        r = classify_zone_by_distance(np.array([0.5, 0.5]), np.array([0.52, 0.53]))
        assert r.zone == "A"

    def test_between_radii_is_b(self) -> None:
        r = classify_zone_by_distance(np.array([0.5, 0.5]), np.array([0.7, 0.7]))
        assert r.zone == "B"

    def test_beyond_b_is_c(self) -> None:
        r = classify_zone_by_distance(np.array([0.0, 0.0]), np.array([1.0, 1.0]))
        assert r.zone == "C"

    def test_custom_thresholds_respected(self) -> None:
        r = classify_zone_by_distance(
            np.array([0.0, 0.0]), np.array([0.5, 0.0]),
            a_radius_m=1.0, b_radius_m=2.0,
        )
        assert r.zone == "A"

    def test_returns_zone_classification(self) -> None:
        r = classify_zone_by_distance(np.array([0.0, 0.0]), np.array([0.0, 0.0]))
        assert isinstance(r, ZoneClassification)


class TestNextShotBased:
    def test_straight_easy_next_shot_is_a(self) -> None:
        # Cue at (0.1, 1.27), OB at (0.5, 1.27), pocket side-right.
        # Cut angle zero, short travel — textbook A.
        state = _state([
            _ball("cue", (0.1, 1.27)),
            _ball("6", (0.5, 1.27)),
        ])
        r = classify_zone_for_next_shot(state, "6", "side-right")
        assert r.zone == "A"
        assert r.next_shot_plan is not None
        assert r.next_shot_plan.cut_angle_deg < 1e-6

    def test_wide_cut_next_shot_is_c(self) -> None:
        # Cue placed well off the OB→pocket line: cut angle > 60°.
        state = _state([
            _ball("cue", (1.2, 1.35)),
            _ball("6", (0.6, 1.3)),
        ])
        r = classify_zone_for_next_shot(state, "6", "top-left")
        assert r.zone == "C"
        assert r.next_shot_plan is not None
        assert r.next_shot_plan.cut_angle_deg > 60.0

    def test_moderate_cut_is_b(self) -> None:
        # Cut between 30° and 60°, short travel.
        state = _state([
            _ball("cue", (1.1, 1.0)),
            _ball("6", (0.6, 1.3)),
        ])
        r = classify_zone_for_next_shot(state, "6", "top-left")
        assert r.zone == "B"
        assert r.next_shot_plan is not None
        assert 30.0 < r.next_shot_plan.cut_angle_deg <= 60.0

    def test_long_travel_downgrades_a_to_b(self) -> None:
        # Straight shot, but cue is far from OB — over the long-travel threshold.
        state = _state([
            _ball("cue", (0.1, 1.27)),
            _ball("6", (1.2, 1.27)),  # 1.1 m away, still side-right
        ])
        # Shot is straight (A by angle) but travel is only ~1.04m - actually
        # let's place the shot so travel > 1.5 m.
        state = _state([
            _ball("cue", (0.1, 0.1)),
            _ball("6", (0.1, 1.9)),
        ])
        r = classify_zone_for_next_shot(state, "6", "top-left")
        # cut ≈ 0, travel > 1.5 m → B
        assert r.zone == "B"

    def test_blocker_forces_c(self) -> None:
        state = _state([
            _ball("cue", (0.1, 1.27)),
            _ball("6", (0.9, 1.27)),
            _ball("blocker", (0.5, 1.27)),
        ])
        r = classify_zone_for_next_shot(state, "6", "side-right")
        assert r.zone == "C"
        assert "blocker" in r.reason

    def test_unsolvable_shot_is_c(self) -> None:
        # Cue past the OB relative to pocket — cut >= 90°.
        state = _state([
            _ball("cue", (0.8, 1.27)),
            _ball("6", (0.5, 1.27)),
        ])
        r = classify_zone_for_next_shot(state, "6", "side-right")
        assert r.zone == "C"
        assert "not playable" in r.reason

    def test_reason_is_non_empty_for_all_zones(self) -> None:
        state = _state([
            _ball("cue", (0.1, 1.27)),
            _ball("6", (0.5, 1.27)),
        ])
        r = classify_zone_for_next_shot(state, "6", "side-right")
        assert r.reason != ""


class TestCustomThresholds:
    def test_strict_a_threshold_pushes_to_b(self) -> None:
        # Borderline straight shot becomes B if A threshold tightened to 1°.
        state = _state([
            _ball("cue", (0.1, 1.25)),
            _ball("6", (0.5, 1.27)),
        ])
        r = classify_zone_for_next_shot(
            state, "6", "side-right",
            a_cut_max_deg=1.0, b_cut_max_deg=60.0,
        )
        assert r.zone == "B"
