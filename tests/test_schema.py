"""Tests for the pillar schema loader and validator."""
from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from poolsauce import (
    DEFAULT_SCHEMA_PATH,
    load_pillar_schema,
    validate_pillar_output,
)


VALID_MINIMAL = {
    "shot_id": "test-shot-001",
    "pillar_I": {
        "target": "6-ball",
        "pocket": "top-left",
        "destination": {
            "descriptor": "center-table, high side of the 7",
        },
    },
    "pillar_II": {
        "line_of_aim": {"description": "slight right-to-left cut, ~22°"},
        "contact_point": {"description": "8 o'clock, just under half-ball"},
        "escape_route": {"description": "bottom rail one diamond from right pocket"},
        "rails_involved": ["bottom"],
        "speed_window": {"label": "medium"},
    },
    "pillar_III": {
        "english": {"sauce_term": "a pinch of right"},
        "stroke": {"type": "follow"},
        "force": "measured dose",
        "acceleration": "controlled",
        "recipe_rationale": "widen the rebound, carry into A zone.",
    },
}


def test_schema_file_exists() -> None:
    assert DEFAULT_SCHEMA_PATH.is_file()


def test_schema_loads_and_is_valid_json_schema() -> None:
    schema = load_pillar_schema()
    # Raises if the schema itself does not conform to Draft 2020-12.
    Draft202012Validator.check_schema(schema)


def test_schema_top_level_requires_three_pillars() -> None:
    schema = load_pillar_schema()
    assert set(schema["required"]) == {"shot_id", "pillar_I", "pillar_II", "pillar_III"}


def test_minimal_valid_output_passes() -> None:
    validate_pillar_output(VALID_MINIMAL)


def test_missing_shot_id_fails() -> None:
    bad = copy.deepcopy(VALID_MINIMAL)
    del bad["shot_id"]
    with pytest.raises(ValidationError):
        validate_pillar_output(bad)


def test_invalid_pocket_enum_fails() -> None:
    bad = copy.deepcopy(VALID_MINIMAL)
    bad["pillar_I"]["pocket"] = "under-the-table"
    with pytest.raises(ValidationError):
        validate_pillar_output(bad)


def test_invalid_speed_label_fails() -> None:
    bad = copy.deepcopy(VALID_MINIMAL)
    bad["pillar_II"]["speed_window"]["label"] = "light speed"
    with pytest.raises(ValidationError):
        validate_pillar_output(bad)


def test_canonical_first_conversation_output_validates() -> None:
    """The Turn-2 pillar output from first_conversation.md serializes cleanly."""
    canonical = {
        "shot_id": "ep01-shot-01",
        "pillar_I": {
            "target": "6-ball",
            "pocket": "top-left",
            "destination": {
                "descriptor": (
                    "lower-center, high side of the 7 — roughly half a diamond "
                    "above the bottom rail, giving a natural angle into the "
                    "bottom-right corner on the next shot"
                ),
            },
            "intention_pure": True,
        },
        "pillar_II": {
            "line_of_aim": {"description": "slight right-to-left cut, approximately 22°"},
            "contact_point": {
                "description": "8 o'clock on the object ball — just under a half-ball hit",
                "ball_fraction": 0.45,
            },
            "escape_route": {
                "description": (
                    "cue ball travels down and slightly right after contact, "
                    "catches the bottom rail one diamond from the right pocket, "
                    "returns into the lower-center zone"
                ),
            },
            "rails_involved": ["bottom"],
            "speed_window": {"label": "medium", "m_per_s": 2.2},
        },
        "pillar_III": {
            "english": {"sauce_term": "a pinch of right", "tips_offset": 0.25},
            "stroke": {"type": "follow", "sauce_term": "a zest of follow"},
            "force": "measured dose",
            "acceleration": "controlled",
            "recipe_rationale": (
                "the pinch of right widens the rebound off the bottom rail; "
                "the zest of follow carries the cue ball off the cushion with "
                "enough life to settle in the A zone without drifting into the "
                "B zone above it."
            ),
        },
        "doctrine_line": "The warrior seasons the strike, never guesses.",
    }
    validate_pillar_output(canonical)
