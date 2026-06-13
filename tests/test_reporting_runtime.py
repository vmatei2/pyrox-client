"""Focused tests for the reporting runtime seam.

These tests cover behaviour below the FastAPI adapter: database path
resolution, DuckDB runtime health access, and direct use of the reporting query
module against a temporary DuckDB artifact.
"""

from pathlib import Path

import duckdb
import pytest

from pyrox_api_service.database import (
    DatabaseConfigurationError,
    DuckDBRuntime,
    resolve_database_path,
)
from pyrox_api_service.reporting_queries import ReportingQueries


def test_resolve_database_path_uses_relative_cwd(tmp_path: Path) -> None:
    """Relative database paths resolve against the supplied working directory."""
    db_path = tmp_path / "pyrox.duckdb"
    db_path.touch()

    assert resolve_database_path("pyrox.duckdb", cwd=tmp_path) == str(db_path)


def test_resolve_database_path_rejects_missing_file(tmp_path: Path) -> None:
    """Missing database artifacts fail before request handling reaches DuckDB."""
    with pytest.raises(DatabaseConfigurationError, match="DuckDB file not found"):
        resolve_database_path("missing.duckdb", cwd=tmp_path)


def test_runtime_lists_tables_from_configured_duckdb(tmp_path: Path) -> None:
    """DuckDBRuntime exposes table names from its configured artifact."""
    db_path = tmp_path / "runtime.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE race_results (result_id VARCHAR);")
    con.close()

    runtime = DuckDBRuntime(database_path=str(db_path))

    assert runtime.list_tables() == ["race_results"]


def test_reporting_queries_can_run_without_fastapi_adapter(tmp_path: Path) -> None:
    """ReportingQueries can be exercised directly through the runtime seam."""
    db_path = tmp_path / "queries.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE race_results (
            result_id VARCHAR,
            season INTEGER,
            location VARCHAR,
            year INTEGER,
            division VARCHAR,
            gender VARCHAR,
            age_group VARCHAR,
            total_time_min DOUBLE
        );
        """
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("r1", 8, "london", 2024, "open", "F", "30-34", 60.0),
            ("r2", 8, "paris", 2024, "open", "female", "30-34", 62.0),
        ],
    )
    con.close()

    queries = ReportingQueries(DuckDBRuntime(database_path=str(db_path)))

    payload = queries.distribution(gender="female", division="open", season=8)

    assert payload["cohort"]["season"] == 8
    assert payload["n"] == 2
    assert payload["histogram"]["count"] == 2
