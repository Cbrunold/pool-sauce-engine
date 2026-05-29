"""Tests for Unit H — the CLI."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from poolsauce.cli import (
    build_parser,
    format_debrief,
    format_pillar_plan,
    load_state_from_json,
    main,
)


def _write_state(tmp_path: Path, cue=(0.1, 1.27), ob=(0.5, 1.27)) -> Path:
    state = {
        "table_size_m": [2.54, 1.27],
        "balls": [
            {"id": "cue", "x_m": cue[0], "y_m": cue[1]},
            {"id": "6", "x_m": ob[0], "y_m": ob[1]},
        ],
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


class TestLoadState:
    def test_basic_load(self, tmp_path: Path) -> None:
        path = _write_state(tmp_path)
        state = load_state_from_json(path)
        assert state.cue_ball.id == "cue"
        np.testing.assert_allclose(state.cue_ball.position, [0.1, 1.27])

    def test_missing_cue_rejected(self, tmp_path: Path) -> None:
        data = {"balls": [{"id": "6", "x_m": 0.5, "y_m": 1.0}]}
        path = tmp_path / "state.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="cue"):
            load_state_from_json(path)

    def test_duplicate_ids_rejected(self, tmp_path: Path) -> None:
        data = {
            "balls": [
                {"id": "cue", "x_m": 0.1, "y_m": 1.0},
                {"id": "cue", "x_m": 0.5, "y_m": 1.0},
            ],
        }
        path = tmp_path / "state.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="duplicate"):
            load_state_from_json(path)


class TestPlanCommand:
    def test_plan_prints_all_pillars(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        path = _write_state(tmp_path)
        rc = main([
            "plan",
            "--state", str(path),
            "--target", "6",
            "--pocket", "side-right",
            "--destination", "center-table for the 7",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "PILLAR I" in out
        assert "PILLAR II" in out
        assert "PILLAR III" in out
        assert "PILLAR IV" in out
        assert "Target:       6" in out
        assert "Pocket:       side-right" in out

    def test_plan_with_english_and_stroke(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        path = _write_state(tmp_path)
        rc = main([
            "plan",
            "--state", str(path),
            "--target", "6",
            "--pocket", "side-right",
            "--destination", "center-table",
            "--english", "drop of right",
            "--stroke", "zest of follow",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "drop of right" in out
        assert "zest of follow" in out

    def test_plan_json_emits_valid_structure(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        path = _write_state(tmp_path)
        rc = main([
            "plan",
            "--state", str(path),
            "--target", "6",
            "--pocket", "side-right",
            "--destination", "center-table",
            "--dest-xy", "0.5", "1.27",
            "--json",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["shot_id"] == "cli-shot"
        assert data["pillar_I"]["target"] == "6"

    def test_doctrine_line_rendered_in_plan(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        path = _write_state(tmp_path)
        rc = main([
            "plan",
            "--state", str(path),
            "--target", "6",
            "--pocket", "side-right",
            "--destination", "center-table",
            "--doctrine", "The warrior seasons the strike.",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "The warrior seasons the strike." in out

    def test_invalid_pocket_rejected_by_argparse(self, tmp_path: Path) -> None:
        path = _write_state(tmp_path)
        with pytest.raises(SystemExit):
            main([
                "plan", "--state", str(path),
                "--target", "6", "--pocket", "nope", "--destination", "x",
            ])


class TestDebriefCommand:
    def test_debrief_adds_pillar_V(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        state_path = _write_state(tmp_path)
        # Produce a plan JSON first.
        main([
            "plan",
            "--state", str(state_path),
            "--target", "6",
            "--pocket", "side-right",
            "--destination", "center-table",
            "--dest-xy", "0.5", "1.27",
            "--shot-id", "debrief-cli-1",
            "--json",
        ])
        plan_json = capsys.readouterr().out
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(plan_json, encoding="utf-8")

        rc = main([
            "debrief",
            "--plan", str(plan_path),
            "--state", str(state_path),
            "--json",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        debrief = json.loads(out)
        assert "pillar_V" in debrief
        assert debrief["pillar_V"]["zone_landing"]["zone"] in {"A", "B", "C"}

    def test_debrief_text_contains_section(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        state_path = _write_state(tmp_path)
        main([
            "plan",
            "--state", str(state_path),
            "--target", "6",
            "--pocket", "side-right",
            "--destination", "center-table",
            "--dest-xy", "0.5", "1.27",
            "--json",
        ])
        plan_json = capsys.readouterr().out
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(plan_json, encoding="utf-8")

        rc = main([
            "debrief",
            "--plan", str(plan_path),
            "--state", str(state_path),
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "PILLAR V" in out
        assert "Zone landing" in out
        assert "Mastery 1%" in out


class TestFormatters:
    def test_format_pillar_plan_is_multiline(self) -> None:
        plan = {
            "pillar_I": {
                "target": "6",
                "pocket": "side-right",
                "destination": {"descriptor": "center"},
            },
            "pillar_II": {
                "line_of_aim": {"description": "aim"},
                "contact_point": {"description": "center ball"},
                "escape_route": {"description": "stun tangent"},
                "rails_involved": ["none"],
                "speed_window": {"label": "medium", "m_per_s": 1.2},
            },
            "pillar_III": {
                "english": {"sauce_term": "none", "tips_offset": 0.0},
                "stroke": {"type": "stun", "sauce_term": "spoon of stun",
                           "tips_offset_vertical": 0.0},
                "force": "measured dose",
                "acceleration": "controlled",
                "recipe_rationale": "center ball, clean.",
            },
        }
        text = format_pillar_plan(plan)
        assert "PILLAR I" in text
        assert "medium (1.20 m/s)" in text
        assert "(Yours, warrior.)" in text
