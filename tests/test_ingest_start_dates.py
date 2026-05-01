from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pytest

from scripts.ingest_duckdb_from_s3 import (
    apply_event_start_dates,
    load_event_start_date_mapping,
)


def _write_json(path: Path, payload: dict[str, str]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_load_event_start_date_mapping_parses_season_files(tmp_path: Path):
    _write_json(
        tmp_path / "EVENT_START_DATES_SEASON_7.json",
        {
            "HYROX New Delhi 2025 / Naib Dilli": "2025-07-19T00:00:00",
            "HYROX Sao Paulo 2025": "2025-09-20T00:00:00",
        },
    )
    _write_json(
        tmp_path / "EVENT_START_DATES_SEASON_8.json",
        {"HYROX Ghent 2025 / Gent": "2025-12-12T00:00:00"},
    )

    mapping = load_event_start_date_mapping(tmp_path)

    assert mapping[(7, "new-delhi", 2025)] == date(2025, 7, 19)
    assert mapping[(7, "sao-paulo", 2025)] == date(2025, 9, 20)
    assert mapping[(8, "ghent", 2025)] == date(2025, 12, 12)


def test_load_event_start_date_mapping_fails_on_conflicting_dates(tmp_path: Path):
    _write_json(
        tmp_path / "EVENT_START_DATES_SEASON_8.json",
        {
            "HYROX Sao Paulo 2026": "2026-04-25T00:00:00",
            "HYROX São Paulo 2026 / Sao Paulo": "2026-05-25T00:00:00",
        },
    )

    with pytest.raises(RuntimeError, match="Conflicting start_date mapping"):
        load_event_start_date_mapping(tmp_path)


def test_apply_event_start_dates_populates_with_aliases():
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE race_results (
            season INTEGER,
            location VARCHAR,
            year INTEGER
        );
        """
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?)",
        [
            (8, "delhi", 2025),
            (8, "london-excel", 2025),
            (8, "lisboa", 2026),
            (8, "paris-gp", 2026),
            (7, "miami-beach", 2025),
        ],
    )

    apply_event_start_dates(
        con,
        {
            (8, "new-delhi", 2025): date(2025, 7, 19),
            (8, "london", 2025): date(2025, 12, 4),
            (8, "lisbon", 2026): date(2026, 5, 1),
            (8, "paris", 2026): date(2026, 4, 27),
            (7, "miami", 2025): date(2025, 4, 19),
        },
    )

    rows = con.execute(
        """
        SELECT season, location, year, start_date
        FROM race_results
        ORDER BY season, location
        """
    ).fetchall()
    assert rows == [
        (7, "miami-beach", 2025, date(2025, 4, 19)),
        (8, "delhi", 2025, date(2025, 7, 19)),
        (8, "lisboa", 2026, date(2026, 5, 1)),
        (8, "london-excel", 2025, date(2025, 12, 4)),
        (8, "paris-gp", 2026, date(2026, 4, 27)),
    ]


def test_apply_event_start_dates_fails_for_unmapped_event():
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE race_results (
            season INTEGER,
            location VARCHAR,
            year INTEGER
        );
        """
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?)",
        [
            (8, "unknown-city", 2025),
            (8, "delhi", 2025),
        ],
    )

    with pytest.raises(RuntimeError, match="Missing start_date mappings"):
        apply_event_start_dates(
            con,
            {
                (8, "new-delhi", 2025): date(2025, 7, 19),
            },
        )
