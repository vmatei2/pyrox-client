"""API endpoint tests backed by temporary DuckDB fixtures.

Each test seeds only the tables needed for its endpoint and validates key
response fields to keep contract checks fast and focused.
"""

from pathlib import Path
import importlib

import duckdb
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from pyrox_api_service import app as api  # noqa: E402


def _create_db(path: Path) -> duckdb.DuckDBPyConnection:
    """Create an isolated on-disk DuckDB connection for one test case."""
    return duckdb.connect(str(path))


def test_legacy_api_shim_points_to_new_service_module():
    """Ensure legacy import shims still resolve to the active API service."""
    legacy_package = importlib.import_module("src.pyrox.api")
    legacy_module = importlib.import_module("src.pyrox.api.app")
    new_module = importlib.import_module("pyrox_api_service.app")

    assert legacy_package.app.title == new_module.app.title
    assert legacy_module.app.title == new_module.app.title


def _seed_search_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Seed the minimum schema and rows needed by the athlete search endpoint."""
    con.execute(
        """
        CREATE TABLE athlete_index (
            athlete_id VARCHAR,
            canonical_name VARCHAR,
            name_lc VARCHAR,
            gender VARCHAR,
            nationality VARCHAR,
            race_count INTEGER
        );
        """
    )
    con.execute(
        """
        CREATE TABLE athlete_results (
            athlete_id VARCHAR,
            result_id VARCHAR
        );
        """
    )
    con.execute(
        """
        CREATE TABLE race_results (
            result_id VARCHAR,
            event_id VARCHAR,
            season INTEGER,
            location VARCHAR,
            year INTEGER,
            name VARCHAR,
            division VARCHAR,
            gender VARCHAR,
            total_time_min DOUBLE
        );
        """
    )
    con.executemany(
        "INSERT INTO athlete_index VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("ath_1", "james ingham", "james ingham", "M", "GB", 2),
        ],
    )
    con.executemany(
        "INSERT INTO athlete_results VALUES (?, ?)",
        [
            ("ath_1", "result_1"),
            ("ath_1", "result_2"),
        ],
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("result_1", "event_1", 8, "london", 2024, "James Ingham", "open", "M", 62.0),
            ("result_2", "event_2", 8, "manchester", 2024, "James Ingham", "open", "M", 64.0),
        ],
    )


def _seed_report_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Seed report/ranking/split tables for /api/reports endpoint coverage."""
    con.execute(
        """
        CREATE TABLE race_results (
            result_id VARCHAR,
            event_id VARCHAR,
            season INTEGER,
            location VARCHAR,
            year INTEGER,
            division VARCHAR,
            gender VARCHAR,
            age_group VARCHAR,
            name VARCHAR,
            total_time_min DOUBLE,
            work_time_min DOUBLE,
            run_time_min DOUBLE,
            roxzone_time_min DOUBLE,
            run1_time_min DOUBLE,
            run2_time_min DOUBLE,
            run3_time_min DOUBLE,
            run4_time_min DOUBLE,
            run5_time_min DOUBLE,
            run6_time_min DOUBLE,
            run7_time_min DOUBLE
        );
        """
    )
    con.execute(
        """
        CREATE TABLE race_rankings (
            result_id VARCHAR,
            event_rank INTEGER,
            event_size INTEGER,
            event_percentile DOUBLE,
            season_rank INTEGER,
            season_size INTEGER,
            season_percentile DOUBLE,
            overall_rank INTEGER,
            overall_size INTEGER,
            overall_percentile DOUBLE
        );
        """
    )
    con.execute(
        """
        CREATE TABLE split_percentiles (
            result_id VARCHAR,
            split_name VARCHAR,
            split_time_min DOUBLE,
            split_rank INTEGER,
            split_size INTEGER,
            split_percentile DOUBLE,
            location VARCHAR,
            division VARCHAR,
            gender VARCHAR,
            age_group VARCHAR
        );
        """
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "result_1",
                "event_1",
                8,
                "london",
                2024,
                "open",
                "F",
                "30-34",
                "Kate Russell",
                62.0,
                36.0,
                22.0,
                4.0,
                3.4,
                3.6,
                3.5,
                3.8,
                3.7,
                3.9,
                4.0,
            ),
            (
                "result_2",
                "event_2",
                8,
                "london",
                2024,
                "open",
                "F",
                "30-34",
                "Jane Doe",
                64.0,
                38.0,
                21.0,
                3.0,
                3.2,
                3.3,
                3.4,
                3.5,
                3.6,
                3.7,
                3.8,
            ),
        ],
    )
    con.executemany(
        "INSERT INTO race_rankings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("result_1", 10, 200, 0.8, 50, 500, 0.9, 200, 5000, 0.96),
        ],
    )
    con.executemany(
        "INSERT INTO split_percentiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("result_1", "run1", 0.5, 1, 2, 1.0, "london", "open", "F", "30-34"),
            ("result_2", "run1", 2.0, 2, 2, 0.0, "london", "open", "F", "30-34"),
            ("result_1", "rowErg", 4.0, 1, 2, 0.8, "london", "open", "F", "30-34"),
            ("result_2", "rowErg", 5.0, 2, 2, 0.2, "london", "open", "F", "30-34"),
        ],
    )


def _seed_planner_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Seed planner rows with controlled distributions for histogram assertions."""
    segment_keys = [config["key"] for config in api.SEGMENT_CONFIG]
    columns = [
        "season INTEGER",
        "location VARCHAR",
        "year INTEGER",
        "division VARCHAR",
        "gender VARCHAR",
        *[f"{key} DOUBLE" for key in segment_keys],
    ]
    con.execute(f"CREATE TABLE race_results ({', '.join(columns)});")

    def build_row(total_time: float, run1_value: float) -> dict:
        row = {
            "season": 8,
            "location": "london",
            "year": 2024,
            "division": "open",
            "gender": "F",
        }
        for index, key in enumerate(segment_keys):
            if key == "total_time_min":
                row[key] = total_time
            elif key == "run1_time_min":
                row[key] = run1_value
            elif key.startswith("run"):
                row[key] = 2.0 + index * 0.1
            else:
                row[key] = 3.0 + index * 0.1
        return row

    rows = [
        build_row(62.0, 0.8),
        build_row(64.0, 1.4),
        build_row(70.0, 1.6),
    ]
    insert_columns = ["season", "location", "year", "division", "gender", *segment_keys]
    placeholders = ", ".join(["?"] * len(insert_columns))
    values = [[row[col] for col in insert_columns] for row in rows]
    con.executemany(
        f"INSERT INTO race_results ({', '.join(insert_columns)}) VALUES ({placeholders})",
        values,
    )


def _seed_deepdive_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Seed multi-location cohort data for deepdive podium scope checks."""
    con.execute(
        """
        CREATE TABLE race_results (
            result_id VARCHAR,
            event_name VARCHAR,
            event_id VARCHAR,
            season INTEGER,
            location VARCHAR,
            year INTEGER,
            division VARCHAR,
            gender VARCHAR,
            age_group VARCHAR,
            name VARCHAR,
            total_time_min DOUBLE
        );
        """
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("athlete_result", "London Open", "evt_london", 8, "london", 2024, "open", "F", "30-34", "Athlete A", 63.0),
            ("r_l_1", "London Open", "evt_london", 8, "london", 2024, "open", "F", "30-34", "A One", 60.0),
            ("r_l_2", "London Open", "evt_london", 8, "london", 2024, "open", "F", "30-34", "B Two", 61.0),
            ("r_l_3", "London Open", "evt_london", 8, "london", 2024, "open", "F", "30-34", "C Three", 62.0),
            ("r_l_4", "London Open", "evt_london", 8, "london", 2024, "open", "F", "30-34", "D Four", 65.0),
            ("r_p_1", "Paris Open", "evt_paris", 8, "paris", 2024, "open", "F", "30-34", "E Five", 59.0),
            ("r_p_2", "Paris Open", "evt_paris", 8, "paris", 2024, "open", "F", "30-34", "F Six", 60.5),
            ("r_p_3", "Paris Open", "evt_paris", 8, "paris", 2024, "open", "F", "30-34", "G Seven", 61.5),
            ("r_p_4", "Paris Open", "evt_paris", 8, "paris", 2024, "open", "F", "30-34", "H Eight", 70.0),
            ("r_other", "London Pro", "evt_other", 8, "london", 2024, "pro", "M", "35-39", "Ignored Athlete", 58.0),
        ],
    )


def test_healthcheck_lists_tables(tmp_path, monkeypatch):
    """Healthcheck should return table visibility for the configured DB."""
    db_path = tmp_path / "health.db"
    con = _create_db(db_path)
    con.execute("CREATE TABLE race_results (result_id VARCHAR);")
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)
    resp = client.get("/api/health")

    assert resp.status_code == 200
    data = resp.json()
    assert "race_results" in data["tables"]


def test_search_endpoint_returns_races(tmp_path, monkeypatch):
    """Search endpoint should return all races linked to a matched athlete."""
    db_path = tmp_path / "search.db"
    con = _create_db(db_path)
    _seed_search_tables(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)
    resp = client.get("/api/athletes/search", params={"name": "James Ingham"})

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 2
    event_ids = {race["event_id"] for race in payload["races"]}
    assert event_ids == {"event_1", "event_2"}


def test_report_endpoint_filters_run_split_min_values(tmp_path, monkeypatch):
    """Report endpoint should apply run split minimum thresholds in cohort stats."""
    db_path = tmp_path / "report.db"
    con = _create_db(db_path)
    _seed_report_tables(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)
    resp = client.get("/api/reports/result_1", params={"split_name": "run1"})

    assert resp.status_code == 200
    payload = resp.json()
    selected_split = payload["distributions"]["selected_split"]
    assert selected_split["cohort"]["count"] == 1
    assert selected_split["stats"]["cohort"]["mean"] == 2.0


def test_report_endpoint_includes_plot_data_series(tmp_path, monkeypatch):
    """Report payload should include derived plotting series with expected values."""
    db_path = tmp_path / "report-plots.db"
    con = _create_db(db_path)
    _seed_report_tables(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)
    resp = client.get("/api/reports/result_1")

    assert resp.status_code == 200
    payload = resp.json()

    work_vs_run = payload["plot_data"]["work_vs_run_split"]
    assert work_vs_run["work_time_min"] == pytest.approx(36.0)
    assert work_vs_run["run_time_with_roxzone_min"] == pytest.approx(26.0)
    assert work_vs_run["work_pct"] == pytest.approx(36.0 / 62.0)
    assert work_vs_run["run_pct"] == pytest.approx(26.0 / 62.0)

    run_change_series = payload["plot_data"]["run_change_series"]
    points = run_change_series["points"]
    assert [point["run"] for point in points] == [
        "Run 2",
        "Run 3",
        "Run 4",
        "Run 5",
        "Run 6",
        "Run 7",
    ]
    assert run_change_series["median_run_time_min"] == pytest.approx(3.75)
    assert points[0]["run_time_min"] == pytest.approx(3.6)
    assert points[0]["delta_from_median_min"] == pytest.approx(3.6 - 3.75)
    assert points[-1]["run_time_min"] == pytest.approx(4.0)
    assert points[-1]["delta_from_median_min"] == pytest.approx(4.0 - 3.75)
    assert run_change_series["count"] == 6
    assert run_change_series["min_delta_min"] == pytest.approx(-0.25)
    assert run_change_series["max_delta_min"] == pytest.approx(0.25)


def test_planner_endpoint_applies_time_and_run_filters(tmp_path, monkeypatch):
    """Planner endpoint should respect both total-time range and segment filters."""
    db_path = tmp_path / "planner.db"
    con = _create_db(db_path)
    _seed_planner_tables(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)
    resp = client.get(
        "/api/planner",
        params={
            "season": 8,
            "location": "london",
            "year": 2024,
            "division": "open",
            "gender": "F",
            "min_total_time": 60,
            "max_total_time": 65,
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 2
    run1_segment = next(
        segment for segment in payload["segments"] if segment["key"] == "run1_time_min"
    )
    total_segment = next(
        segment for segment in payload["segments"] if segment["key"] == "total_time_min"
    )
    assert run1_segment["histogram"]["count"] == 1
    assert total_segment["histogram"]["count"] == 2


def test_deepdive_endpoint_supports_podium_for_all_and_location_scope(tmp_path, monkeypatch):
    """Deepdive should expose podium stats for all-locations and location-only scopes."""
    db_path = tmp_path / "deepdive.db"
    con = _create_db(db_path)
    _seed_deepdive_tables(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)
    base_params = {
        "season": 8,
        "division": "open",
        "gender": "female",
        "age_group": "30-34",
    }

    # Any-location scope: podium is computed across both London and Paris cohorts.
    all_resp = client.get("/api/deepdive/athlete_result", params=base_params)
    assert all_resp.status_code == 200
    all_payload = all_resp.json()
    assert all_payload["total_locations"] == 2
    assert all_payload["group_summary"]["podium"]["count"] == 3
    assert all_payload["group_summary"]["podium"]["max"] == pytest.approx(60.5)
    assert all_payload["group_distribution"]["podium"]["count"] == 3
    all_locations = {row["location"]: row for row in all_payload["locations"]}
    assert all_locations["london"]["podium"] == pytest.approx(62.0)
    assert all_locations["paris"]["podium"] == pytest.approx(61.5)

    # Location scope: podium is recomputed from London-only cohort rows.
    london_resp = client.get(
        "/api/deepdive/athlete_result",
        params={**base_params, "location": "london"},
    )
    assert london_resp.status_code == 200
    london_payload = london_resp.json()
    assert london_payload["filters"]["location"] == "london"
    assert london_payload["total_locations"] == 1
    assert london_payload["group_summary"]["podium"]["count"] == 3
    assert london_payload["group_summary"]["podium"]["max"] == pytest.approx(62.0)
    assert london_payload["group_distribution"]["podium"]["count"] == 3
    assert london_payload["locations"][0]["location"] == "london"
    assert london_payload["locations"][0]["podium"] == pytest.approx(62.0)
