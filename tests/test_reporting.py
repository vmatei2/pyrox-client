import pandas as pd
import pytest

from src.pyrox.errors import AthleteNotFound
from src.pyrox.reporting import ReportingClient


@pytest.fixture
def reporting_client_with_db():
    reporting = ReportingClient(database=":memory:")
    con = reporting._ensure_connection()

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
            name VARCHAR
        );
        """
    )

    con.executemany(
        "INSERT INTO athlete_index VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("ath_1", "james ingham", "james ingham", "M", "GB", 2),
            ("ath_2", "jane doe", "jane doe", "F", "US", 1),
        ],
    )
    con.executemany(
        "INSERT INTO athlete_results VALUES (?, ?)",
        [
            ("ath_1", "result_1"),
            ("ath_1", "result_2"),
            ("ath_2", "result_3"),
        ],
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("result_1", "event_1", 8, "london", 2024, "James Ingham"),
            ("result_2", "event_2", 8, "manchester", 2024, "James Ingham"),
            ("result_3", "event_1", 8, "london", 2024, "Jane Doe"),
        ],
    )

    return reporting


def test_search_athlete_races_returns_dataframe(reporting_client_with_db):
    races = reporting_client_with_db.search_athlete_races("James Ingham")

    assert len(races) == 2
    assert set(races["event_id"]) == {"event_1", "event_2"}
    assert (races["name"] == "James Ingham").all()


def test_search_athlete_races_missing_raises(reporting_client_with_db):
    with pytest.raises(AthleteNotFound):
        reporting_client_with_db.search_athlete_races("Missing Athlete")


def test_search_athlete_races_requires_unique(reporting_client_with_db):
    con = reporting_client_with_db._ensure_connection()
    con.executemany(
        "INSERT INTO athlete_index VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("ath_3", "james ingham", "james ingham", "M", "US", 1),
        ],
    )
    con.executemany(
        "INSERT INTO athlete_results VALUES (?, ?)",
        [
            ("ath_3", "result_4"),
        ],
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("result_4", "event_3", 8, "berlin", 2024, "James Ingham"),
        ],
    )

    with pytest.raises(ValueError):
        reporting_client_with_db.search_athlete_races("James Ingham")

    races = reporting_client_with_db.search_athlete_races(
        "James Ingham",
        nationality="GB",
    )
    assert len(races) == 2

    races = reporting_client_with_db.search_athlete_races(
        "James Ingham",
        require_unique=False,
    )
    assert len(races) == 3
    assert set(races["event_id"]) == {"event_1", "event_2", "event_3"}
