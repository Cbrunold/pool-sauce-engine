"""Pydantic request/response models — mirrors pillars.schema.json."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

class BallIn(BaseModel):
    id: str
    x_m: float
    y_m: float


class TableStateIn(BaseModel):
    table_size_m: tuple[float, float] = (2.54, 1.27)
    balls: list[BallIn]

    model_config = {"extra": "ignore"}


# ---------------------------------------------------------------------------
# /api/plan
# ---------------------------------------------------------------------------

class IntentionIn(BaseModel):
    target_ball_id: str
    pocket: Literal[
        "top-left", "top-right", "bottom-left", "bottom-right",
        "side-left", "side-right"
    ]
    destination_descriptor: str
    destination_coordinates_m: tuple[float, float] | None = None
    destination_tolerance_m: float | None = None


class SauceIn(BaseModel):
    english: str = "none"
    stroke: str = "spoon of stun"
    force: Literal["soft", "measured", "firm", "break"] = "measured"
    acceleration: Literal["decelerating", "controlled", "accelerating"] = "controlled"
    recipe_rationale: str | None = None
    speed_margin: float = 1.15
    # Manual spin override in raw tips (−1..1). When set, overrides phrases.
    vertical_tips: float | None = None    # + follow / − draw
    horizontal_tips: float | None = None  # + right / − left


class PlanRequest(BaseModel):
    state: TableStateIn
    intention: IntentionIn
    sauce: SauceIn = Field(default_factory=SauceIn)
    cue_ball_id: str = "cue"
    shot_id: str = "web-shot"
    doctrine_line: str | None = None
    # 0 = direct shot; 1/2/3 = force a bank of that many rails.
    bank_rails: int = 0
    # When true and a destination coordinate is given, the engine derives the
    # spin/speed that lands the cue on the leave instead of defaulting to stun.
    optimize_sauce: bool = False


class PlanResponse(BaseModel):
    plan: dict[str, Any]


# ---------------------------------------------------------------------------
# /api/debrief
# ---------------------------------------------------------------------------

class DebriefOverridesIn(BaseModel):
    spin_verdict: Literal[
        "clean", "too much", "not enough", "wrong axis", "overcooked", "undercooked"
    ] = "clean"
    spin_notes: str = ""
    pace_control: Literal[
        "clean", "punchy", "decelerated", "floated", "stunned-late", "stunned-early"
    ] | None = None
    correct_side: Literal["high", "low", "natural", "forced"] = "natural"
    risk_zones_crossed: list[str] = Field(default_factory=list)
    mastery_excellent: str = "Commitment through the shot."
    mastery_fragile: str = "One more ounce of patience."


class DebriefRequest(BaseModel):
    plan: dict[str, Any]
    actual_cue_position_m: tuple[float, float] | None = None
    overrides: DebriefOverridesIn = Field(default_factory=DebriefOverridesIn)


class DebriefResponse(BaseModel):
    plan: dict[str, Any]


# ---------------------------------------------------------------------------
# /api/detect
# ---------------------------------------------------------------------------

class DetectedBall(BaseModel):
    id: str | None = None           # None when color unrecognised
    x_m: float
    y_m: float
    color_hsv: tuple[float, float, float]
    confidence: float               # 0–1
    needs_confirm: bool             # True when confidence < 0.7
    radius_px: int


class DetectResponse(BaseModel):
    balls: list[DetectedBall]
    table_corners_px: list[tuple[int, int]] | None = None
    width_px: int
    height_px: int


# ---------------------------------------------------------------------------
# /api/cue-options — ranked strokes to an exact cue destination
# ---------------------------------------------------------------------------

class CueOptionsRequest(BaseModel):
    state: TableStateIn
    intention: IntentionIn          # target ball + pocket; destination used as exact target
    target_position_m: tuple[float, float]
    cue_ball_id: str = "cue"
    tolerance_m: float = 0.18
    max_options: int = 6


class RankedOption(BaseModel):
    rank: int
    difficulty_label: str           # stock | comfortable | tricky | hard
    difficulty: float
    makeable: bool
    english: str                    # Sauce phrase
    stroke: str                     # Sauce phrase
    vertical_tips: float
    horizontal_tips: float
    speed_margin: float
    predicted_landing_m: tuple[float, float]
    landing_error_m: float


class CueOptionsResponse(BaseModel):
    options: list[RankedOption]
