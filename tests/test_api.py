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
            ("r_b_1", "Berlin Pro", "evt_berlin", 8, "berlin", 2024, "pro", "M", "35-39", "I Nine", 57.5),
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
    assert {race["athlete_id"] for race in payload["races"]} == {"ath_1"}


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


def test_rankings_endpoint_returns_top_rows_and_time_lookup(tmp_path, monkeypatch):
    """Rankings should sort by fastest times and return lookup placement for a target time."""
    db_path = tmp_path / "rankings.db"
    con = _create_db(db_path)
    _seed_deepdive_tables(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)
    resp = client.get(
        "/api/rankings",
        params={
            "season": 8,
            "division": "open",
            "gender": "female",
            "age_group": "30-34",
            "limit": 3,
            "target_time_min": 61.0,
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 9
    assert payload["total_locations"] == 2
    assert len(payload["rows"]) == 3

    first_row = payload["rows"][0]
    assert first_row["placement"] == 1
    assert first_row["name"] == "E Five"
    assert first_row["total_time_min"] == pytest.approx(59.0)
    assert first_row["location"] == "paris"

    location_rows = {row["location"]: row for row in payload["locations"]}
    assert location_rows["london"]["count"] == 5
    assert location_rows["paris"]["count"] == 4
    assert location_rows["london"]["fastest_time_min"] == pytest.approx(60.0)
    assert location_rows["paris"]["fastest_time_min"] == pytest.approx(59.0)

    lookup = payload["placement_lookup"]
    assert lookup["target_time_min"] == pytest.approx(61.0)
    assert lookup["placement"] == 4
    assert lookup["out_of"] == 9
    assert lookup["exact_matches"] == 1


def test_rankings_filters_endpoint_exposes_age_groups_and_filtered_locations(tmp_path, monkeypatch):
    """Rankings filters should return age-groups and locations for required scope."""
    db_path = tmp_path / "rankings-filters.db"
    con = _create_db(db_path)
    _seed_deepdive_tables(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)

    all_resp = client.get(
        "/api/rankings/filters",
        params={"season": 8, "division": "open", "gender": "female"},
    )
    assert all_resp.status_code == 200
    all_payload = all_resp.json()
    assert all_payload["age_groups"] == ["30-34"]
    assert all_payload["locations"] == ["london", "paris"]

    filtered_resp = client.get(
        "/api/rankings/filters",
        params={
            "season": 8,
            "division": "open",
            "gender": "female",
            "age_group": "30-34",
        },
    )
    assert filtered_resp.status_code == 200
    filtered_payload = filtered_resp.json()
    assert filtered_payload["filters"]["age_group"] == "30-34"
    assert filtered_payload["locations"] == ["london", "paris"]


def test_rankings_endpoint_requires_division_and_gender(tmp_path, monkeypatch):
    """Rankings endpoint should enforce mandatory division and gender query params."""
    db_path = tmp_path / "rankings-required.db"
    con = _create_db(db_path)
    _seed_deepdive_tables(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)

    missing_division = client.get("/api/rankings", params={"season": 8, "gender": "female"})
    assert missing_division.status_code == 422

    missing_gender = client.get("/api/rankings", params={"season": 8, "division": "open"})
    assert missing_gender.status_code == 422


def test_rankings_endpoint_supports_db_name_search_without_losing_global_placement(
    tmp_path, monkeypatch
):
    """Athlete-name filter should search DB rows while keeping global placement numbers."""
    db_path = tmp_path / "rankings-athlete-search.db"
    con = _create_db(db_path)
    _seed_deepdive_tables(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)

    resp = client.get(
        "/api/rankings",
        params={
            "season": 8,
            "division": "open",
            "gender": "female",
            "age_group": "30-34",
            "athlete_name": "Athlete A",
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 9
    assert payload["filters"]["athlete_name"] == "Athlete A"
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["name"] == "Athlete A"
    assert payload["rows"][0]["placement"] == 7


def test_rankings_endpoint_name_search_returns_empty_rows_when_not_found(tmp_path, monkeypatch):
    """Unknown athlete searches should return an empty rows list instead of a hard API error."""
    db_path = tmp_path / "rankings-empty-name-search.db"
    con = _create_db(db_path)
    _seed_deepdive_tables(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)

    resp = client.get(
        "/api/rankings",
        params={
            "season": 8,
            "division": "open",
            "gender": "female",
            "age_group": "30-34",
            "athlete_name": "No Such Athlete",
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 9
    assert payload["rows"] == []


# ── Athlete Profile ────────────────────────────────────────────────────────────


def _seed_profile_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Seed tables required for GET /api/athletes/profile tests."""
    con.execute(
        """
        CREATE TABLE race_results (
            result_id VARCHAR,
            event_id  VARCHAR,
            season    INTEGER,
            location  VARCHAR,
            year      INTEGER,
            division  VARCHAR,
            gender    VARCHAR,
            age_group VARCHAR,
            name      VARCHAR,
            total_time_min          DOUBLE,
            run_time_min            DOUBLE,
            roxzone_time_min        DOUBLE,
            skiErg_time_min         DOUBLE,
            sledPush_time_min       DOUBLE,
            sledPull_time_min       DOUBLE,
            burpeeBroadJump_time_min DOUBLE,
            rowErg_time_min         DOUBLE,
            farmersCarry_time_min   DOUBLE,
            sandbagLunges_time_min  DOUBLE,
            wallBalls_time_min      DOUBLE
        );
        """
    )
    con.execute(
        """
        CREATE TABLE race_rankings (
            result_id        VARCHAR,
            event_rank       INTEGER,
            event_size       INTEGER,
            event_percentile DOUBLE,
            season_rank      INTEGER,
            season_size      INTEGER,
            season_percentile DOUBLE,
            overall_rank     INTEGER,
            overall_size     INTEGER,
            overall_percentile DOUBLE
        );
        """
    )
    con.execute(
        """
        CREATE TABLE athlete_index (
            athlete_id     VARCHAR,
            canonical_name VARCHAR,
            name_lc        VARCHAR,
            gender         VARCHAR,
            nationality    VARCHAR,
            race_count     INTEGER
        );
        """
    )
    con.execute(
        """
        CREATE TABLE athlete_results (
            athlete_id VARCHAR,
            result_id  VARCHAR
        );
        """
    )

    # Two races for "Sarah Johnson" (different events, different years)
    con.executemany(
        """
        INSERT INTO race_results VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            # result_id, event_id, season, location, year, division, gender, age_group,
            # name, total, run_time, roxzone, skiErg, sledPush, sledPull, burpee, rowErg, farmers, sandbag, wallBalls
            ("r1", "evt1", 8, "Vienna",  2025, "Open", "Female", "F30-34",
             "Sarah Johnson", 84.55, 39.2, 4.6, 4.35, 5.1, 5.2, 3.8, 5.5, 4.0, 4.2, 3.9),
            ("r2", "evt2", 7, "Berlin",  2024, "Open", "Female", "F30-34",
             "Sarah Johnson", 86.20, 40.5, 4.8, 4.50, 5.3, 5.4, 3.9, 5.7, 4.1, 4.3, 4.0),
        ],
    )
    # One race for a different athlete (must not appear in Sarah's profile)
    con.executemany(
        """
        INSERT INTO race_results VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("r3", "evt1", 8, "Vienna", 2025, "Open", "Male", "M30-34",
             "John Smith", 90.0, 41.5, 5.0, 4.8, 5.5, 5.6, 4.0, 6.0, 4.5, 4.8, 4.3),
            ("r4", "evt1", 8, "Vienna", 2025, "Open", "Female", "F30-34",
             "Faster Rival", 82.0, 38.2, 4.4, 4.2, 4.9, 5.0, 3.6, 5.2, 3.8, 4.0, 3.7),
            ("r5", "evt2", 7, "Berlin", 2024, "Open", "Female", "F30-34",
             "Slower Rival", 89.0, 42.0, 5.1, 4.8, 5.6, 5.7, 4.2, 6.1, 4.6, 4.9, 4.4),
        ],
    )
    con.executemany(
        "INSERT INTO race_rankings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("r1", 2, 3, 0.5, 30, 600, 0.95, 100, 5000, 0.98),
            ("r2", 1, 2, 1.0, 40, 550, 0.93, 120, 4800, 0.97),
        ],
    )
    con.executemany(
        "INSERT INTO athlete_index VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("ath_sarah", "sarah johnson", "sarah johnson", "Female", "USA", 2),
        ],
    )
    con.executemany(
        "INSERT INTO athlete_results VALUES (?, ?)",
        [
            ("ath_sarah", "r1"),
            ("ath_sarah", "r2"),
        ],
    )


def _make_profile_client(tmp_path, monkeypatch, suffix="profile"):
    db_path = tmp_path / f"{suffix}.db"
    con = _create_db(db_path)
    _seed_profile_tables(con)
    con.close()
    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    return TestClient(api.app)


def test_profile_returns_200_for_known_athlete(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    resp = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"})
    assert resp.status_code == 200


def test_profile_by_id_returns_200_for_known_athlete(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    resp = client.get("/api/athletes/ath_sarah/profile")
    assert resp.status_code == 200
    assert resp.json()["athlete"]["athlete_id"] == "ath_sarah"


def test_profile_by_id_returns_404_for_unknown_athlete(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    resp = client.get("/api/athletes/ath_missing/profile")
    assert resp.status_code == 404


def test_profile_returns_404_for_unknown_athlete(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    resp = client.get("/api/athletes/profile", params={"name": "Ghost Runner"})
    assert resp.status_code == 404


def test_profile_athlete_fields(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    athlete = payload["athlete"]
    assert athlete["name"] == "Sarah Johnson"
    assert athlete["gender"] == "Female"
    assert athlete["division"] == "Open"
    assert athlete["age_group"] == "F30-34"


def test_profile_nationality_from_athlete_index(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    assert payload["athlete"]["nationality"] == "USA"


def test_profile_summary_total_races(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    assert payload["summary"]["total_races"] == 2


def test_profile_by_id_filters_by_division(tmp_path, monkeypatch):
    db_path = tmp_path / "profile-divisions.db"
    con = _create_db(db_path)
    _seed_profile_tables(con)
    con.execute(
        """
        INSERT INTO race_results VALUES
        (
            'r6', 'evt3', 8, 'Paris', 2025, 'Pro', 'Female', 'F30-34',
            'Sarah Johnson', 83.10, 38.4, 4.3, 4.20, 4.9, 5.0, 3.5, 5.1, 3.7, 3.9, 3.6
        )
        """
    )
    con.execute("INSERT INTO race_rankings VALUES ('r6', 1, 2, 1.0, 10, 200, 0.98, 50, 3000, 0.99)")
    con.execute("INSERT INTO athlete_results VALUES ('ath_sarah', 'r6')")
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)

    all_payload = client.get("/api/athletes/ath_sarah/profile").json()
    assert all_payload["available_divisions"] == ["Open", "Pro"]
    assert all_payload["filters"]["division"] is None
    assert all_payload["summary"]["total_races"] == 3

    open_payload = client.get(
        "/api/athletes/ath_sarah/profile",
        params={"division": "Open"},
    ).json()
    assert open_payload["filters"]["division"] == "Open"
    assert open_payload["summary"]["total_races"] == 2
    assert open_payload["athlete"]["division"] == "Open"
    assert {race["result_id"] for race in open_payload["races"]} == {"r1", "r2"}
    assert open_payload["summary"]["best_overall_time"] == pytest.approx(84.55)

    pro_payload = client.get(
        "/api/athletes/ath_sarah/profile",
        params={"division": "Pro"},
    ).json()
    assert pro_payload["filters"]["division"] == "Pro"
    assert pro_payload["summary"]["total_races"] == 1
    assert pro_payload["athlete"]["division"] == "Pro"
    assert {race["result_id"] for race in pro_payload["races"]} == {"r6"}
    assert pro_payload["summary"]["best_overall_time"] == pytest.approx(83.10)


def test_profile_by_id_returns_404_for_missing_division(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    resp = client.get("/api/athletes/ath_sarah/profile", params={"division": "Doubles"})
    assert resp.status_code == 404
    assert "Doubles" in resp.json()["detail"]


def test_profile_summary_best_overall_time(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    assert payload["summary"]["best_overall_time"] == pytest.approx(84.55)


def test_profile_summary_best_age_group_finish(tmp_path, monkeypatch):
    """Best AG finish should reflect DB event/age-group rankings."""
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    assert payload["summary"]["best_age_group_finish"] == 1


def test_profile_summary_first_season(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    assert payload["summary"]["first_season"] == "2024"


def test_profile_personal_bests_overall(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    pb = payload["personal_bests"]
    assert "overall" in pb
    assert pb["overall"]["time"] == pytest.approx(84.55)
    assert pb["overall"]["result_id"] == "r1"
    assert pb["overall"]["year"] == 2025


def test_profile_personal_bests_station_present(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    pb = payload["personal_bests"]
    assert "skierg" in pb
    assert pb["skierg"]["time"] == pytest.approx(4.35)
    assert pb["skierg"]["result_id"] == "r1"


def test_profile_personal_bests_include_run_plus_roxzone(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    pb = payload["personal_bests"]
    assert "runplusroxzone" in pb
    assert pb["runplusroxzone"]["time"] == pytest.approx(43.8)
    assert pb["runplusroxzone"]["result_id"] == "r1"


def test_profile_average_times_include_run_plus_roxzone(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    averages = payload["average_times"]
    assert averages["overall"]["time"] == pytest.approx((84.55 + 86.20) / 2)
    assert averages["runplusroxzone"]["time"] == pytest.approx((43.8 + 45.3) / 2)
    assert averages["skierg"]["time"] == pytest.approx((4.35 + 4.50) / 2)


def test_profile_personal_bests_empty_when_no_station_data(tmp_path, monkeypatch):
    """If race_results has no station columns, personal_bests should only have 'overall'."""
    db_path = tmp_path / "profile-nostations.db"
    con = _create_db(db_path)
    # Minimal schema without station columns
    con.execute(
        """
        CREATE TABLE race_results (
            result_id VARCHAR, event_id VARCHAR, season INTEGER,
            location VARCHAR, year INTEGER, division VARCHAR,
            gender VARCHAR, age_group VARCHAR, name VARCHAR,
            total_time_min DOUBLE
        );
        """
    )
    con.execute("CREATE TABLE race_rankings (result_id VARCHAR)")
    con.execute("CREATE TABLE athlete_results (athlete_id VARCHAR, result_id VARCHAR)")
    con.execute(
        "CREATE TABLE athlete_index (athlete_id VARCHAR, canonical_name VARCHAR, "
        "name_lc VARCHAR, gender VARCHAR, nationality VARCHAR, race_count INTEGER)"
    )
    con.execute(
        "INSERT INTO race_results VALUES ('r1', 'e1', 8, 'Vienna', 2025, 'Open', 'F', 'F30-34', 'Mini Athlete', 84.0)"
    )
    con.execute("INSERT INTO athlete_results VALUES ('ath_mini', 'r1')")
    con.execute(
        "INSERT INTO athlete_index VALUES ('ath_mini', 'mini athlete', 'mini athlete', 'F', 'USA', 1)"
    )
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)
    payload = client.get("/api/athletes/profile", params={"name": "Mini Athlete"}).json()
    pb = payload["personal_bests"]
    averages = payload["average_times"]
    # Only the overall key (from total_time_min) should appear; no station keys
    assert set(pb.keys()) == {"overall"}
    assert set(averages.keys()) == {"overall"}


def test_profile_seasons_grouped_by_year_ascending(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    seasons = payload["seasons"]
    assert len(seasons) == 2
    assert seasons[0]["season"] == "2024"
    assert seasons[1]["season"] == "2025"
    assert seasons[0]["best_time"] == pytest.approx(86.20)
    assert seasons[1]["best_time"] == pytest.approx(84.55)


def test_profile_races_ordered_year_desc(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    races = payload["races"]
    assert len(races) == 2
    assert races[0]["year"] == 2025
    assert races[1]["year"] == 2024


def test_profile_races_age_group_rank(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    ranks = {r["result_id"]: r["age_group_rank"] for r in payload["races"]}
    assert ranks["r1"] == 2
    assert ranks["r2"] == 1


def test_profile_ranks_are_sourced_from_race_rankings_table(tmp_path, monkeypatch):
    db_path = tmp_path / "profile-rank-source.db"
    con = _create_db(db_path)
    _seed_profile_tables(con)
    con.execute("UPDATE race_rankings SET event_rank = 42 WHERE result_id = 'r1'")
    con.execute("UPDATE race_rankings SET event_rank = 99 WHERE result_id = 'r2'")
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    client = TestClient(api.app)
    payload = client.get("/api/athletes/profile", params={"name": "Sarah Johnson"}).json()
    ranks = {r["result_id"]: r["age_group_rank"] for r in payload["races"]}
    assert ranks["r1"] == 42
    assert ranks["r2"] == 99
    assert payload["summary"]["best_age_group_finish"] == 42


def test_profile_name_match_is_case_insensitive(tmp_path, monkeypatch):
    client = _make_profile_client(tmp_path, monkeypatch)
    resp = client.get("/api/athletes/profile", params={"name": "sarah johnson"})
    assert resp.status_code == 200
    assert resp.json()["summary"]["total_races"] == 2
