import duckdb
import pytest

from scripts import sql_queries


def test_create_race_rankings_percentiles():
    con = duckdb.connect()
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
            total_time_min DOUBLE
        );
        """
    )
    con.executemany(
        """
        INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("r1", "event_1", 8, "london", 2024, "open", "M", "30-34", 60.0),
            ("r2", "event_1", 8, "london", 2024, "open", "M", "30-34", 70.0),
            ("r3", "event_1", 8, "london", 2024, "open", "M", "30-34", 80.0),
            ("r4", "event_2", 8, "london", 2024, "open", "M", "30-34", 65.0),
            ("r5", "event_3", 7, "paris", 2023, "open", "M", "30-34", 75.0),
        ],
    )

    con.execute(sql_queries.CREATE_RACE_RANKINGS)
    results = con.execute(
        """
        SELECT
            result_id,
            event_rank,
            event_size,
            event_percentile,
            season_size,
            season_percentile,
            overall_size,
            overall_percentile
        FROM race_rankings
        ORDER BY result_id
        """
    ).fetchdf()

    row_r1 = results[results["result_id"] == "r1"].iloc[0]
    assert row_r1["event_rank"] == 1
    assert row_r1["event_size"] == 4
    assert row_r1["event_percentile"] == pytest.approx(1.0)
    assert row_r1["season_size"] == 4
    assert row_r1["overall_size"] == 5
    assert row_r1["overall_percentile"] == pytest.approx(1.0)

    row_r3 = results[results["result_id"] == "r3"].iloc[0]
    assert row_r3["event_rank"] == 4
    assert row_r3["event_percentile"] == pytest.approx(0.0)
    assert row_r3["season_percentile"] == pytest.approx(0.0)
    assert row_r3["overall_percentile"] == pytest.approx(0.0)

    row_r4 = results[results["result_id"] == "r4"].iloc[0]
    assert row_r4["event_rank"] == 2
    assert row_r4["event_size"] == 4
    assert row_r4["event_percentile"] == pytest.approx(2.0 / 3.0)
    assert row_r4["season_percentile"] == pytest.approx(2.0 / 3.0)
    assert row_r4["overall_percentile"] == pytest.approx(0.75)

    row_r5 = results[results["result_id"] == "r5"].iloc[0]
    assert row_r5["season_size"] == 1
    assert row_r5["season_percentile"] == pytest.approx(1.0)


def test_create_split_percentiles_runs_and_stations():
    con = duckdb.connect()
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
            run1_time_min DOUBLE,
            run2_time_min DOUBLE,
            run3_time_min DOUBLE,
            run4_time_min DOUBLE,
            run5_time_min DOUBLE,
            run6_time_min DOUBLE,
            run7_time_min DOUBLE,
            run8_time_min DOUBLE,
            skiErg_time_min DOUBLE,
            sledPush_time_min DOUBLE,
            sledPull_time_min DOUBLE,
            burpeeBroadJump_time_min DOUBLE,
            rowErg_time_min DOUBLE,
            farmersCarry_time_min DOUBLE,
            sandbagLunges_time_min DOUBLE,
            wallBalls_time_min DOUBLE,
            roxzone_time_min DOUBLE,
            run_time_min DOUBLE,
            work_time_min DOUBLE
        );
        """
    )
    con.executemany(
        """
        INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "r1",
                "event_1",
                8,
                "london",
                2024,
                "open",
                "M",
                "30-34",
                5.0,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                3.0,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                1.5,
                40.0,
                20.0,
            ),
            (
                "r2",
                "event_1",
                8,
                "london",
                2024,
                "open",
                "M",
                "30-34",
                6.0,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                4.0,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                2.0,
                42.0,
                22.0,
            ),
            (
                "r3",
                "event_2",
                8,
                "london",
                2024,
                "open",
                "M",
                "30-34",
                5.5,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                3.5,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                1.7,
                41.0,
                21.0,
            ),
        ],
    )

    con.execute(sql_queries.CREATE_SPLIT_PERCENTILES)
    results = con.execute(
        """
        SELECT result_id, split_name, split_rank, split_size, split_percentile
        FROM split_percentiles
        WHERE split_name IN ('run_1', 'ski_erg')
        ORDER BY split_name, result_id
        """
    ).fetchdf()

    run_rows = results[results["split_name"] == "run_1"]
    assert run_rows["split_size"].tolist() == [3, 3, 3]
    run_r1_pct = run_rows.loc[run_rows["result_id"] == "r1", "split_percentile"].iloc[0]
    run_r2_pct = run_rows.loc[run_rows["result_id"] == "r2", "split_percentile"].iloc[0]
    run_r3_pct = run_rows.loc[run_rows["result_id"] == "r3", "split_percentile"].iloc[0]
    assert run_r1_pct == pytest.approx(1.0)
    assert run_r3_pct == pytest.approx(0.5)
    assert run_r2_pct == pytest.approx(0.0)

    ski_rows = results[results["split_name"] == "ski_erg"]
    assert ski_rows["split_size"].tolist() == [3, 3, 3]
    ski_r1_pct = ski_rows.loc[ski_rows["result_id"] == "r1", "split_percentile"].iloc[0]
    ski_r2_pct = ski_rows.loc[ski_rows["result_id"] == "r2", "split_percentile"].iloc[0]
    ski_r3_pct = ski_rows.loc[ski_rows["result_id"] == "r3", "split_percentile"].iloc[0]
    assert ski_r1_pct == pytest.approx(1.0)
    assert ski_r3_pct == pytest.approx(0.5)
    assert ski_r2_pct == pytest.approx(0.0)


def test_create_athlete_history_includes_rankings():
    con = duckdb.connect()
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
            total_time_min DOUBLE
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
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("r1", "event_1", 8, "london", 2024, "open", "M", "30-34", "A One", 60.0),
            ("r2", "event_1", 8, "london", 2024, "open", "M", "30-34", "B Two", 70.0),
        ],
    )
    con.executemany(
        "INSERT INTO athlete_results VALUES (?, ?)",
        [
            ("ath_1", "r1"),
            ("ath_1", "r2"),
        ],
    )

    con.execute(sql_queries.CREATE_RACE_RANKINGS)
    con.execute(sql_queries.CREATE_ATHLETE_HISTORY)
    results = con.execute(
        """
        SELECT athlete_id, result_id, event_percentile
        FROM athlete_history
        ORDER BY result_id
        """
    ).fetchdf()

    assert results["athlete_id"].unique().tolist() == ["ath_1"]
    assert results["result_id"].tolist() == ["r1", "r2"]
    assert results["event_percentile"].tolist() == pytest.approx([1.0, 0.0])
