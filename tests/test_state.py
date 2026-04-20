"""Tests for the Unit A state model."""
from __future__ import annotations

import numpy as np
import pytest

from poolsauce import (
    BALL_RADIUS_M,
    POCKET_NAMES,
    TABLE_9FT_LENGTH_M,
    TABLE_9FT_WIDTH_M,
    Ball,
    Table,
    TableState,
)


class TestBall:
    def test_defaults_are_zero_motion(self) -> None:
        b = Ball(id="cue", position=[0.3, 0.4])
        assert b.id == "cue"
        np.testing.assert_array_equal(b.position, np.array([0.3, 0.4]))
        np.testing.assert_array_equal(b.velocity, np.zeros(2))
        np.testing.assert_array_equal(b.angular_velocity, np.zeros(3))
        assert b.radius_m == BALL_RADIUS_M
        assert b.is_stationary

    def test_coerces_sequences_to_numpy(self) -> None:
        b = Ball(id="1", position=(0.1, 0.2), velocity=[1.0, 0.0])
        assert isinstance(b.position, np.ndarray)
        assert isinstance(b.velocity, np.ndarray)
        assert b.position.dtype == float

    def test_full_3d_spin(self) -> None:
        b = Ball(
            id="1",
            position=[0.5, 1.0],
            angular_velocity=[2.0, -3.0, 5.0],
        )
        assert b.angular_velocity.shape == (3,)
        np.testing.assert_array_equal(b.angular_velocity, np.array([2.0, -3.0, 5.0]))

    def test_moving_ball_is_not_stationary(self) -> None:
        b = Ball(id="1", position=[0.5, 1.0], velocity=[0.1, 0.0])
        assert not b.is_stationary

    def test_spinning_ball_is_not_stationary(self) -> None:
        b = Ball(id="1", position=[0.5, 1.0], angular_velocity=[0.0, 0.0, 1.0])
        assert not b.is_stationary

    def test_position_must_be_2d(self) -> None:
        with pytest.raises(ValueError, match="position"):
            Ball(id="1", position=[0.1, 0.2, 0.3])

    def test_angular_velocity_must_be_3d(self) -> None:
        with pytest.raises(ValueError, match="angular_velocity"):
            Ball(id="1", position=[0.1, 0.2], angular_velocity=[0.0, 0.0])

    def test_negative_radius_rejected(self) -> None:
        with pytest.raises(ValueError, match="radius_m"):
            Ball(id="1", position=[0.1, 0.2], radius_m=-0.01)


class TestTable:
    def test_default_9ft_dimensions(self) -> None:
        t = Table()
        assert t.length_m == TABLE_9FT_LENGTH_M
        assert t.width_m == TABLE_9FT_WIDTH_M

    def test_pocket_count_and_names(self) -> None:
        t = Table()
        pockets = t.pockets
        assert set(pockets.keys()) == set(POCKET_NAMES)
        assert len(pockets) == 6

    def test_corner_pocket_positions(self) -> None:
        t = Table(length_m=2.54, width_m=1.27)
        np.testing.assert_allclose(t.pockets["bottom-left"], [0.0, 0.0])
        np.testing.assert_allclose(t.pockets["bottom-right"], [1.27, 0.0])
        np.testing.assert_allclose(t.pockets["top-left"], [0.0, 2.54])
        np.testing.assert_allclose(t.pockets["top-right"], [1.27, 2.54])

    def test_side_pocket_positions_are_midway(self) -> None:
        t = Table(length_m=2.54, width_m=1.27)
        np.testing.assert_allclose(t.pockets["side-left"], [0.0, 1.27])
        np.testing.assert_allclose(t.pockets["side-right"], [1.27, 1.27])

    def test_contains(self) -> None:
        t = Table()
        assert t.contains([0.5, 1.0])
        assert t.contains([0.0, 0.0])
        assert not t.contains([-0.1, 0.5])
        assert not t.contains([0.5, 3.0])

    def test_contains_with_margin(self) -> None:
        t = Table()
        assert not t.contains([0.0, 0.0], margin_m=BALL_RADIUS_M)
        assert t.contains([BALL_RADIUS_M, BALL_RADIUS_M], margin_m=BALL_RADIUS_M)

    def test_length_must_exceed_width(self) -> None:
        with pytest.raises(ValueError, match="length_m"):
            Table(length_m=1.0, width_m=1.27)


class TestTableState:
    def _make(self) -> TableState:
        return TableState(
            table=Table(),
            balls=[
                Ball(id="cue", position=[0.635, 1.905]),
                Ball(id="6", position=[0.5, 1.5]),
                Ball(id="7", position=[0.8, 0.3]),
            ],
        )

    def test_get_ball_by_id(self) -> None:
        s = self._make()
        assert s.get_ball("6").id == "6"

    def test_cue_ball_shortcut(self) -> None:
        s = self._make()
        assert s.cue_ball.id == "cue"

    def test_object_balls_excludes_cue(self) -> None:
        s = self._make()
        ids = [b.id for b in s.object_balls()]
        assert "cue" not in ids
        assert set(ids) == {"6", "7"}

    def test_missing_ball_raises(self) -> None:
        s = self._make()
        with pytest.raises(KeyError):
            s.get_ball("99")

    def test_duplicate_ids_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate"):
            TableState(
                table=Table(),
                balls=[
                    Ball(id="cue", position=[0.1, 0.1]),
                    Ball(id="cue", position=[0.2, 0.2]),
                ],
            )
