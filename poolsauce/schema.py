"""Pillar schema loader and validator.

The schema file `pillars.schema.json` at the repo root is the data contract
between Rōnin and every downstream consumer. Every computed pillar output
must validate against it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA_PATH: Path = _REPO_ROOT / "pillars.schema.json"


def load_pillar_schema(path: Path | None = None) -> dict[str, Any]:
    """Load and return the pillar JSON schema as a dict."""
    schema_path = path if path is not None else DEFAULT_SCHEMA_PATH
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_pillar_output(
    output: dict[str, Any],
    schema: dict[str, Any] | None = None,
) -> None:
    """Validate a pillar output dict. Raises jsonschema.ValidationError on failure."""
    resolved = schema if schema is not None else load_pillar_schema()
    Draft202012Validator(resolved).validate(output)
