"""Table and ball state — the v0 data model.

Coordinate convention (see DECISIONS D-011):
- Origin at bottom-left corner of playing surface.
- x: width direction (short side), default extent 1.27 m.
- y: length direction (long side), default extent 2.54 m.
- z: up from cloth (implicit; v0 motion is planar at z = ball_radius).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from poolsauce.constants import (
    BALL_BALL_FRICTION,
    BALL_BALL_RESTITUTION,
    BALL_MASS_KG,
    BALL_RADIUS_M,
    CLOTH_ROLLING_FRICTION,
    CLOTH_SLIDING_FRICTION,
    CLOTH_SPINNING_FRICTION,
    CUSHION_EFFICIENCY,
    CUSHION_SIDE_ENGLISH_COUPLING,
    CUSHION_SIDE_ENGLISH_LOSS,
    CUSHION_TANGENTIAL_PACE_FALLOFF,
    CUSHION_TANGENTIAL_RETENTION,
    CUSHION_TANGENTIAL_RETENTION_MIN,
    TABLE_9FT_LENGTH_M,
    TABLE_9FT_WIDTH_M,
)

# Pocket names — match the enum in pillars.schema.json.
POCKET_NAMES: tuple[str, ...] = (
    "bottom-left",
    "bottom-right",
    "top-left",
    "top-right",
    "side-left",
    "side-right",
)


def _vec(values: Iterable[float] | np.ndarray, size: int, name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.shape != (size,):
        raise ValueError(f"{name} must have shape ({size},), got {arr.shape}")
    return arr


@dataclass
class Ball:
    """A single ball.

    position, velocity: 2D numpy arrays in meters and m/s (table plane).
    angular_velocity: 3D world-frame numpy array in rad/s — [ωx, ωy, ωz].
        ωz is the vertical (massé) axis; the horizontal components resolve into
        topspin/backspin and side english relative to velocity direction.
    """

    id: str
    position: np.ndarray
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2))
    angular_velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    radius_m: float = BALL_RADIUS_M
    mass_kg: float = BALL_MASS_KG

    def __post_init__(self) -> None:
        self.position = _vec(self.position, 2, "position")
        self.velocity = _vec(self.velocity, 2, "velocity")
        self.angular_velocity = _vec(self.angular_velocity, 3, "angular_velocity")
        if self.radius_m <= 0:
            raise ValueError("radius_m must be positive")
        if self.mass_kg <= 0:
            raise ValueError("mass_kg must be positive")

    @property
    def is_stationary(self) -> bool:
        return bool(
            np.allclose(self.velocity, 0.0) and np.allclose(self.angular_velocity, 0.0)
        )


@dataclass
class Table:
    """Playing surface geometry, pocket positions, and cloth parameters."""

    length_m: float = TABLE_9FT_LENGTH_M
    width_m: float = TABLE_9FT_WIDTH_M
    pocket_mouth_m: float = 0.060
    cloth_sliding_friction: float = CLOTH_SLIDING_FRICTION
    cloth_rolling_friction: float = CLOTH_ROLLING_FRICTION
    cloth_spinning_friction: float = CLOTH_SPINNING_FRICTION
    cushion_efficiency: float = CUSHION_EFFICIENCY
    cushion_tangential_retention: float = CUSHION_TANGENTIAL_RETENTION
    cushion_tangential_pace_falloff: float = CUSHION_TANGENTIAL_PACE_FALLOFF
    cushion_tangential_retention_min: float = CUSHION_TANGENTIAL_RETENTION_MIN
    cushion_side_english_coupling: float = CUSHION_SIDE_ENGLISH_COUPLING
    cushion_side_english_loss: float = CUSHION_SIDE_ENGLISH_LOSS
    ball_ball_restitution: float = BALL_BALL_RESTITUTION
    ball_ball_friction: float = BALL_BALL_FRICTION

    def __post_init__(self) -> None:
        if self.length_m <= 0 or self.width_m <= 0:
            raise ValueError("table dimensions must be positive")
        if self.length_m < self.width_m:
            raise ValueError("length_m must be >= width_m (length is the long axis)")
        if self.pocket_mouth_m <= 0:
            raise ValueError("pocket_mouth_m must be positive")

    @property
    def pockets(self) -> dict[str, np.ndarray]:
        """Pocket center positions, keyed by schema pocket name."""
        w, L = self.width_m, self.length_m
        return {
            "bottom-left": np.array([0.0, 0.0]),
            "bottom-right": np.array([w, 0.0]),
            "top-left": np.array([0.0, L]),
            "top-right": np.array([w, L]),
            "side-left": np.array([0.0, L / 2.0]),
            "side-right": np.array([w, L / 2.0]),
        }

    def contains(self, position: np.ndarray, margin_m: float = 0.0) -> bool:
        """Whether a 2D point lies inside the playing surface (with optional inset)."""
        x, y = _vec(position, 2, "position")
        return bool(
            margin_m <= x <= self.width_m - margin_m
            and margin_m <= y <= self.length_m - margin_m
        )


@dataclass
class TableState:
    """A snapshot of the table: geometry plus the balls on it."""

    table: Table
    balls: list[Ball]

    def __post_init__(self) -> None:
        ids = [b.id for b in self.balls]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate ball ids: {ids}")

    def get_ball(self, ball_id: str) -> Ball:
        for b in self.balls:
            if b.id == ball_id:
                return b
        raise KeyError(f"no ball with id={ball_id!r}")

    @property
    def cue_ball(self) -> Ball:
        return self.get_ball("cue")

    def object_balls(self) -> list[Ball]:
        return [b for b in self.balls if b.id != "cue"]
