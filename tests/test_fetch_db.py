"""Tests for the boot-time DuckDB artifact fetch.

The service no longer bakes the database into the image; it downloads the
artifact referenced by the pipeline-published latest.json pointer.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest
import respx

from pyrox_api_service.fetch_db import (
    SUPPORTED_SCHEMA_VERSION,
    ArtifactFetchError,
    ArtifactPointer,
    artifact_url,
    fetch_artifact,
    parse_pointer,
)

POINTER_URL = "https://cdn.example.com/db/latest.json"
DB_BYTES = b"duckdb artifact bytes"


def _pointer_payload(**overrides) -> dict:
    payload = {
        "bucket": "hyrox-results",
        "key": "db/pyrox_duckdb_20260709T123000Z.duckdb",
        "sha256": hashlib.sha256(DB_BYTES).hexdigest(),
        "size_bytes": len(DB_BYTES),
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "built_at": "2026-07-09T12:30:00+00:00",
        "source_s3_uri": "s3://hyrox-results/processed/parquet/*",
        "published_at": "2026-07-09T13:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def test_parse_pointer_happy_path():
    pointer = parse_pointer(_pointer_payload())

    assert pointer == ArtifactPointer(
        key="db/pyrox_duckdb_20260709T123000Z.duckdb",
        sha256=hashlib.sha256(DB_BYTES).hexdigest(),
        size_bytes=len(DB_BYTES),
        schema_version=SUPPORTED_SCHEMA_VERSION,
        built_at="2026-07-09T12:30:00+00:00",
    )


@pytest.mark.parametrize("missing", ["key", "sha256", "size_bytes", "schema_version"])
def test_parse_pointer_rejects_missing_fields(missing: str):
    payload = _pointer_payload()
    del payload[missing]

    with pytest.raises(ArtifactFetchError, match=missing):
        parse_pointer(payload)


def test_parse_pointer_rejects_newer_schema():
    payload = _pointer_payload(schema_version=SUPPORTED_SCHEMA_VERSION + 1)

    with pytest.raises(ArtifactFetchError, match="schema_version"):
        parse_pointer(payload)


def test_artifact_url_joins_key_to_pointer_origin():
    assert (
        artifact_url(POINTER_URL, "db/pyrox_duckdb_20260709T123000Z.duckdb")
        == "https://cdn.example.com/db/pyrox_duckdb_20260709T123000Z.duckdb"
    )


@respx.mock
def test_fetch_artifact_downloads_and_verifies(tmp_path: Path):
    target = tmp_path / "pyrox_duckdb"
    respx.get(POINTER_URL).respond(200, json=_pointer_payload())
    respx.get("https://cdn.example.com/db/pyrox_duckdb_20260709T123000Z.duckdb").respond(
        200, content=DB_BYTES
    )

    pointer = fetch_artifact(POINTER_URL, target)

    assert target.read_bytes() == DB_BYTES
    assert pointer.sha256 == hashlib.sha256(DB_BYTES).hexdigest()


@respx.mock
def test_fetch_artifact_rejects_checksum_mismatch(tmp_path: Path):
    target = tmp_path / "pyrox_duckdb"
    respx.get(POINTER_URL).respond(200, json=_pointer_payload(sha256="0" * 64))
    respx.get("https://cdn.example.com/db/pyrox_duckdb_20260709T123000Z.duckdb").respond(
        200, content=DB_BYTES
    )

    with pytest.raises(ArtifactFetchError, match="sha256"):
        fetch_artifact(POINTER_URL, target)

    assert not target.exists(), "corrupt download must not be swapped into place"


@respx.mock
def test_fetch_artifact_skips_download_when_current(tmp_path: Path):
    target = tmp_path / "pyrox_duckdb"
    target.write_bytes(DB_BYTES)
    respx.get(POINTER_URL).respond(200, json=_pointer_payload())
    artifact_route = respx.get(
        "https://cdn.example.com/db/pyrox_duckdb_20260709T123000Z.duckdb"
    ).respond(200, content=DB_BYTES)

    pointer = fetch_artifact(POINTER_URL, target)

    assert not artifact_route.called
    assert pointer.key == "db/pyrox_duckdb_20260709T123000Z.duckdb"


@respx.mock
def test_fetch_artifact_surfaces_pointer_http_errors(tmp_path: Path):
    respx.get(POINTER_URL).respond(503)

    with pytest.raises(httpx.HTTPStatusError):
        fetch_artifact(POINTER_URL, tmp_path / "pyrox_duckdb")
