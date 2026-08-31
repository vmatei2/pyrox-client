"""Tests for the weekly production-pointer promotion decision."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pyrox_api_service.fetch_db import SUPPORTED_SCHEMA_VERSION, ArtifactFetchError
from scripts.data_promotion import assess_promotion, load_pointer


def _pointer(*, content: bytes = b"candidate", **overrides) -> dict:
    payload = {
        "key": "db/pyrox_duckdb_20260831T120000Z.duckdb",
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "built_at": "2026-08-31T12:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def test_unchanged_sha_is_a_no_op() -> None:
    pointer = _pointer()

    decision = assess_promotion(pointer, pointer)

    assert decision.promote is False


def test_different_sha_is_promotable() -> None:
    candidate = _pointer(content=b"candidate")
    current = _pointer(content=b"current")

    decision = assess_promotion(candidate, current)

    assert decision.promote is True
    assert decision.candidate.sha256 == candidate["sha256"]


def test_malformed_candidate_is_rejected() -> None:
    candidate = _pointer()
    del candidate["sha256"]

    with pytest.raises(ArtifactFetchError, match="sha256"):
        assess_promotion(candidate, _pointer(content=b"current"))


def test_unsupported_candidate_schema_is_rejected() -> None:
    candidate = _pointer(schema_version=SUPPORTED_SCHEMA_VERSION + 1)

    with pytest.raises(ArtifactFetchError, match="newer than supported"):
        assess_promotion(candidate, _pointer(content=b"current"))


def test_invalid_json_is_rejected(tmp_path: Path) -> None:
    pointer_path = tmp_path / "pointer.json"
    pointer_path.write_text("not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="could not read pointer JSON"):
        load_pointer(pointer_path)


def test_non_object_json_is_rejected(tmp_path: Path) -> None:
    pointer_path = tmp_path / "pointer.json"
    pointer_path.write_text(json.dumps([_pointer()]), encoding="utf-8")

    with pytest.raises(ValueError, match="must be an object"):
        load_pointer(pointer_path)
