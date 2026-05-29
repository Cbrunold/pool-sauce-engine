"""Unit D — Sauce translator (Pillar III in code).

Bidirectional mapping between physical tip-offset parameters and the Sauce
vocabulary Rōnin uses to speak about spin. The forward direction — tips
→ cue-ball ω — drives forward simulation. The reverse — ω or tips → nearest
Sauce phrase — drives the plan output text.

Conventions
-----------
- Stroke direction is a 2D unit vector ``d̂`` in the table plane.
- Vertical tip offset is signed: positive = above center (follow-side),
  negative = below center (draw-side). Units are "tips" — one tip equals
  ``TIP_FRACTION_OF_R`` of the ball radius in meters. The tip fraction is
  a calibration knob; the API does not change when it is retuned.
- Horizontal tip offset is signed: positive = player's right (right english),
  negative = player's left. Units are tips.
- Angular velocity imparted to the ball from an offset stroke follows the
  impulse-torque formula ``ω = 2.5 · v · b / R²``, where ``b`` is the offset
  in meters and ``v`` is the stroke speed.
- Side-english axis is ``+ẑ`` (CCW from above is positive ω_z). Right english
  produces positive ω_z.
- Vertical-english axis is ``ẑ × d̂`` — the in-plane direction 90° CCW from
  the stroke. Follow (above-center strike) produces a positive magnitude along
  this axis. For a ``+ŷ`` stroke, that axis is ``-x̂``, and the rolling
  constraint for +y motion is ``ω_x = -v/R`` — so follow matches rolling's
  sign, as expected.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from poolsauce.state import Ball


# One "tip" of offset is this fraction of the ball radius. Cue tips are
# typically 12-14 mm diameter (radius 6-7 mm) against a 28.6 mm ball
# radius — roughly 0.21. We round to 0.20 for a clean calibration anchor.
TIP_FRACTION_OF_R: float = 0.20


# Stroke (vertical english): positive = follow-side, negative = draw-side.
SAUCE_STROKE: dict[str, float] = {
    "spoon of stun":    0.00,
    "zest of follow":  +0.25,
    "full follow":     +1.00,
    "whisper of draw": -0.25,
    "full draw":       -1.00,
}


# English (horizontal side-spin): positive = right, negative = left.
SAUCE_ENGLISH: dict[str, float] = {
    "none":                    0.00,
    "pinch of right":         +0.25,
    "pinch of left":          -0.25,
    "drop of right":          +0.50,
    "drop of left":           -0.50,
    "healthy pour of right": +1.00,
    "healthy pour of left":  -1.00,
}


@dataclass(frozen=True)
class SaucePrescription:
    """The Sauce-language description of a stroke's spin recipe."""
    english: str
    stroke: str
    horizontal_tips: float
    vertical_tips: float


def stroke_to_cue_state(
    cue: Ball,
    direction: np.ndarray,
    speed_m_s: float,
    vertical_tips: float = 0.0,
    horizontal_tips: float = 0.0,
) -> Ball:
    """Build the cue-ball state from a stroke specification.

    Linear velocity equals ``speed_m_s · direction``. Angular velocity is
    computed from the impulse-torque formula. Cue deflection ("squirt") and
    throw-off from the stick are not modeled — true only for modest offsets;
    extreme english can skew the line of aim by 1-3° in real shots.
    """
    direction = np.asarray(direction, dtype=float).reshape(2)
    d_norm = float(np.linalg.norm(direction))
    if not math.isclose(d_norm, 1.0, abs_tol=1e-9):
        raise ValueError(f"direction must be a unit vector, got |d|={d_norm}")
    if speed_m_s < 0:
        raise ValueError("speed must be non-negative")

    R = cue.radius_m
    v_2d = direction * speed_m_s

    b_vert = vertical_tips * TIP_FRACTION_OF_R * R
    b_horiz = horizontal_tips * TIP_FRACTION_OF_R * R

    # Magnitudes — ω = 2.5 · v · b / R².
    omega_vert_mag = 2.5 * speed_m_s * b_vert / (R * R)
    omega_z = 2.5 * speed_m_s * b_horiz / (R * R)

    # Vertical-english axis: ẑ × d̂ (90° CCW of d̂ in the plane).
    vertical_axis_2d = np.array([-direction[1], direction[0]])

    w = np.zeros(3)
    w[:2] = omega_vert_mag * vertical_axis_2d
    w[2] = omega_z

    return Ball(
        id=cue.id,
        position=cue.position.copy(),
        velocity=v_2d,
        angular_velocity=w,
        radius_m=cue.radius_m,
        mass_kg=cue.mass_kg,
    )


def cue_state_from_sauce(
    cue: Ball,
    direction: np.ndarray,
    speed_m_s: float,
    english: str = "none",
    stroke: str = "spoon of stun",
) -> Ball:
    """Build the cue-ball state from Sauce phrases.

    Thin wrapper over ``stroke_to_cue_state`` that looks up the tip offsets
    from the Sauce vocabulary. Unknown phrases raise ``KeyError``.
    """
    vertical_tips, horizontal_tips = tip_offsets_from_phrases(english, stroke)
    return stroke_to_cue_state(
        cue=cue,
        direction=direction,
        speed_m_s=speed_m_s,
        vertical_tips=vertical_tips,
        horizontal_tips=horizontal_tips,
    )


def tip_offsets_from_phrases(english: str, stroke: str) -> tuple[float, float]:
    """Look up ``(vertical_tips, horizontal_tips)`` for a pair of Sauce phrases."""
    if stroke not in SAUCE_STROKE:
        raise KeyError(
            f"unknown stroke {stroke!r}; valid: {sorted(SAUCE_STROKE)}"
        )
    if english not in SAUCE_ENGLISH:
        raise KeyError(
            f"unknown english {english!r}; valid: {sorted(SAUCE_ENGLISH)}"
        )
    return SAUCE_STROKE[stroke], SAUCE_ENGLISH[english]


def describe_stroke(
    vertical_tips: float, horizontal_tips: float
) -> SaucePrescription:
    """Pick the nearest Sauce phrases for the given tip offsets."""
    stroke = _nearest_phrase(SAUCE_STROKE, vertical_tips)
    english = _nearest_phrase(SAUCE_ENGLISH, horizontal_tips)
    return SaucePrescription(
        english=english,
        stroke=stroke,
        horizontal_tips=horizontal_tips,
        vertical_tips=vertical_tips,
    )


def angular_velocity_to_tip_offsets(
    angular_velocity: np.ndarray,
    direction: np.ndarray,
    speed_m_s: float,
    ball_radius_m: float,
) -> tuple[float, float]:
    """Invert the impulse-torque formula: ω → (vertical_tips, horizontal_tips).

    Useful for describing an *observed* cue-ball spin in Sauce terms (Pillar V
    chemistry auditing): given the spin we measured, what stroke would have
    produced it?
    """
    if speed_m_s <= 0:
        raise ValueError("speed must be positive to infer tip offsets")

    w = np.asarray(angular_velocity, dtype=float).reshape(3)
    direction = np.asarray(direction, dtype=float).reshape(2)
    R = ball_radius_m

    omega_z = float(w[2])
    b_horiz = omega_z * R * R / (2.5 * speed_m_s)
    horizontal_tips = b_horiz / (TIP_FRACTION_OF_R * R)

    vertical_axis = np.array([-direction[1], direction[0]])
    omega_vert_mag = float(w[:2] @ vertical_axis)
    b_vert = omega_vert_mag * R * R / (2.5 * speed_m_s)
    vertical_tips = b_vert / (TIP_FRACTION_OF_R * R)

    return vertical_tips, horizontal_tips


def _nearest_phrase(vocab: dict[str, float], value: float) -> str:
    return min(vocab.items(), key=lambda kv: abs(kv[1] - value))[0]
