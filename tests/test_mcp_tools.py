"""Tests for the intent-shaped MCP tool functions.

The tools call the FastAPI app in-process (httpx ASGI transport) and shape the
result for an LLM caller. Each test seeds a temporary DuckDB and points the
service at it via PYROX_DUCKDB_PATH, mirroring tests/test_api.py.
"""

from pathlib import Path

import duckdb
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("mcp")

from pyrox_api_service import mcp_tools  # noqa: E402


def _create_db(path: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(path))


def _seed_distribution(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE race_results (
            result_id VARCHAR, season INTEGER, location VARCHAR, year INTEGER,
            division VARCHAR, gender VARCHAR, age_group VARCHAR,
            total_time_min DOUBLE
        );
        """
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("d1", 8, "london", 2024, "open", "F", "30-34", 60.0),
            ("d2", 8, "paris", 2024, "open", "F", "30-34", 62.0),
            ("d3", 8, "london", 2024, "open", "female", "35-39", 64.0),
            ("d4", 8, "london", 2024, "open", "M", "30-34", 55.0),
        ],
    )


def test_get_distribution_tool_returns_cohort_payload(tmp_path, monkeypatch):
    """get_distribution should return the service's cohort distribution payload."""
    db_path = tmp_path / "mcp-distribution.db"
    con = _create_db(db_path)
    _seed_distribution(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    result = mcp_tools.get_distribution(gender="female", season=8, division="open")

    assert result["cohort"]["gender"] == "female"
    assert result["cohort"]["division"] == "open"
    assert result["n"] == 3


def test_tool_returns_error_dict_instead_of_raising(tmp_path, monkeypatch):
    """A service error (e.g. unknown metric) becomes a structured error, not an exception."""
    db_path = tmp_path / "mcp-error.db"
    con = _create_db(db_path)
    _seed_distribution(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    result = mcp_tools.get_distribution(gender="female", season=8, metric="bogus")

    assert result["status_code"] == 400
    assert "error" in result


def _seed_search(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        "CREATE TABLE athlete_index (athlete_id VARCHAR, canonical_name VARCHAR, "
        "name_lc VARCHAR, gender VARCHAR, nationality VARCHAR, race_count INTEGER);"
    )
    con.execute("CREATE TABLE athlete_results (athlete_id VARCHAR, result_id VARCHAR);")
    con.execute(
        "CREATE TABLE race_results (result_id VARCHAR, event_id VARCHAR, season INTEGER, "
        "location VARCHAR, year INTEGER, name VARCHAR, division VARCHAR, gender VARCHAR, "
        "total_time_min DOUBLE);"
    )
    con.execute(
        "INSERT INTO athlete_index VALUES ('ath_1', 'james ingham', 'james ingham', 'M', 'GB', 2);"
    )
    con.executemany(
        "INSERT INTO athlete_results VALUES (?, ?)",
        [("ath_1", "result_1"), ("ath_1", "result_2")],
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("result_1", "event_1", 8, "london", 2024, "James Ingham", "open", "M", 62.0),
            ("result_2", "event_2", 8, "manchester", 2024, "James Ingham", "open", "M", 64.0),
        ],
    )


def test_find_athlete_caps_matches_and_reports_total(tmp_path, monkeypatch):
    """find_athlete returns the true total but only a capped page of matches."""
    db_path = tmp_path / "mcp-search.db"
    con = _create_db(db_path)
    _seed_search(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    result = mcp_tools.find_athlete("James Ingham", limit=1)

    assert result["total"] == 2
    assert result["returned"] == 1
    assert len(result["matches"]) == 1


def _seed_rankings(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        "CREATE TABLE race_results (result_id VARCHAR, event_name VARCHAR, event_id VARCHAR, "
        "season INTEGER, location VARCHAR, year INTEGER, division VARCHAR, gender VARCHAR, "
        "age_group VARCHAR, name VARCHAR, total_time_min DOUBLE);"
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("r1", "London Open", "e1", 8, "london", 2024, "open", "F", "30-34", "A", 60.0),
            ("r2", "London Open", "e1", 8, "london", 2024, "open", "F", "30-34", "B", 61.0),
            ("r3", "London Open", "e1", 8, "london", 2024, "open", "F", "30-34", "C", 62.0),
            ("r4", "Paris Open", "e2", 8, "paris", 2024, "open", "F", "30-34", "D", 63.0),
            ("r5", "Paris Open", "e2", 8, "paris", 2024, "open", "F", "30-34", "E", 64.0),
        ],
    )


def test_get_rankings_respects_limit_but_keeps_full_count(tmp_path, monkeypatch):
    """get_rankings returns the full cohort count but only `limit` rows."""
    db_path = tmp_path / "mcp-rankings.db"
    con = _create_db(db_path)
    _seed_rankings(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    result = mcp_tools.get_rankings(season=8, division="open", gender="female", limit=2)

    assert result["count"] == 5
    assert len(result["rows"]) == 2


def test_get_athlete_profile_requires_name_or_id(tmp_path, monkeypatch):
    """Calling get_athlete_profile with neither identifier returns an error, not a crash."""
    db_path = tmp_path / "mcp-profile-noargs.db"
    con = _create_db(db_path)
    con.execute("CREATE TABLE race_results (result_id VARCHAR);")
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    result = mcp_tools.get_athlete_profile()
    assert result["status_code"] == 400


def test_list_filters_returns_distinct_cohort_values(tmp_path, monkeypatch):
    """list_filters surfaces the distinct seasons/divisions available to query."""
    db_path = tmp_path / "mcp-filters.db"
    con = _create_db(db_path)
    con.execute(
        "CREATE TABLE race_results (result_id VARCHAR, season INTEGER, location VARCHAR, "
        "year INTEGER, division VARCHAR, gender VARCHAR, age_group VARCHAR);"
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("f1", 8, "london", 2024, "open", "F", "30-34"),
            ("f2", 7, "paris", 2023, "pro", "M", "35-39"),
        ],
    )
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    result = mcp_tools.list_filters()
    assert result["seasons"] == [8, 7]
    assert set(result["divisions"]) == {"open", "pro"}


def test_mcp_server_registers_expected_tools():
    """The MCP server should expose exactly the intent-shaped tool set."""
    import asyncio

    from pyrox_api_service import mcp_app

    tools = asyncio.run(mcp_app.mcp_server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "list_filters",
        "find_athlete",
        "get_distribution",
        "get_rankings",
        "get_race_report",
        "get_deepdive",
        "get_athlete_profile",
    }
