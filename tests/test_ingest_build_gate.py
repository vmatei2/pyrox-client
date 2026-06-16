from __future__ import annotations

import duckdb
import pytest

from scripts.ingest_duckdb_from_s3 import (
    INTEGRITY_MIN_ROSTER,
    _enforce_integrity_gate,
    assert_race_results_integrity,
)


def _race_results_con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE race_results (
            season INTEGER,
            location VARCHAR,
            year INTEGER,
            division VARCHAR,
            name_raw VARCHAR,
            roxzone_time_min DOUBLE
        );
        """
    )
    return con


def _insert_rows(
    con: duckdb.DuckDBPyConnection,
    rows: list[tuple[int, str, int, str, str, float | None]],
) -> None:
    con.executemany("INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?)", rows)


def test_clean_data_passes_integrity_gate():
    con = _race_results_con()
    _insert_rows(
        con,
        [
            (8, "london", 2025, "Men Open", f"Athlete {idx}", 1.25)
            for idx in range(INTEGRITY_MIN_ROSTER)
        ],
    )

    assert assert_race_results_integrity(con) == []


def test_fanout_is_caught():
    con = _race_results_con()
    rows = []
    for idx in range(INTEGRITY_MIN_ROSTER):
        rows.append((8, "london", 2025, "Men Open", f"Athlete {idx}", 1.25))
        rows.append((8, "london", 2025, "Men Open", f"Athlete {idx}", 1.25))
    _insert_rows(con, rows)

    violations = assert_race_results_integrity(con)

    assert len(violations) == 1
    assert "fan-out" in violations[0]


def test_zero_roxzone_values_are_allowed():
    con = _race_results_con()
    _insert_rows(
        con,
        [
            (8, "london", 2025, "Women Open", f"Athlete {idx}", 0.0)
            for idx in range(INTEGRITY_MIN_ROSTER)
        ],
    )

    assert assert_race_results_integrity(con) == []


def test_missing_roxzone_values_are_allowed():
    con = _race_results_con()
    _insert_rows(
        con,
        [
            (8, "london", 2025, "Women Open", f"Athlete {idx}", None)
            for idx in range(INTEGRITY_MIN_ROSTER)
        ],
    )

    assert assert_race_results_integrity(con) == []


def test_mixed_missing_and_zero_roxzone_values_are_allowed():
    con = _race_results_con()
    _insert_rows(
        con,
        [
            (8, "london", 2025, "Women Open", f"Athlete {idx}", None)
            for idx in range(INTEGRITY_MIN_ROSTER - 1)
        ]
        + [(8, "london", 2025, "Women Open", "Athlete with zero roxzone", 0.0)],
    )

    assert assert_race_results_integrity(con) == []


def test_small_groups_are_ignored():
    con = _race_results_con()
    _insert_rows(
        con,
        [
            (8, "london", 2025, "Mixed Doubles", "Duplicated Athlete", 0.0)
            for _ in range(INTEGRITY_MIN_ROSTER - 1)
        ],
    )

    assert assert_race_results_integrity(con) == []


def test_integrity_gate_aborts_by_default():
    with pytest.raises(SystemExit, match="Refusing to build DuckDB"):
        _enforce_integrity_gate(
            ["(season=8, location=london, year=2025, division=Men Open): fan-out 2.00"],
            allow_dirty=False,
        )


def test_integrity_gate_honors_allow_dirty():
    _enforce_integrity_gate(
        ["(season=8, location=london, year=2025, division=Men Open): fan-out 2.00"],
        allow_dirty=True,
    )
