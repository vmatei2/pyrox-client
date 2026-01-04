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
            name VARCHAR,
            division VARCHAR
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
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("result_1", "event_1", 8, "london", 2024, "James Ingham", "open"),
            ("result_2", "event_2", 8, "manchester", 2024, "James Ingham", "pro"),
            ("result_3", "event_1", 8, "london", 2024, "Jane Doe", "open"),
        ],
    )

    return reporting


def test_search_athlete_races_returns_dataframe(reporting_client_with_db):
    """Returns two race rows for a unique athlete name."""
    races = reporting_client_with_db.search_athlete_races("James Ingham")

    assert len(races) == 2
    assert set(races["event_id"]) == {"event_1", "event_2"}
    assert (races["name"] == "James Ingham").all()


def test_search_athlete_races_missing_raises(reporting_client_with_db):
    """Raises AthleteNotFound when the athlete name is absent."""
    with pytest.raises(AthleteNotFound):
        reporting_client_with_db.search_athlete_races("Missing Athlete")


def test_search_athlete_races_requires_unique(reporting_client_with_db):
    """Requires disambiguation when multiple athletes share a name."""
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
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("result_4", "event_3", 8, "berlin", 2024, "James Ingham", "open"),
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


def test_search_athlete_races_order_insensitive(reporting_client_with_db):
    """Matches names regardless of order/punctuation."""
    con = reporting_client_with_db._ensure_connection()
    con.executemany(
        "INSERT INTO athlete_index VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("ath_4", "matei, vlad", "matei, vlad", "M", "RO", 1),
        ],
    )
    con.executemany(
        "INSERT INTO athlete_results VALUES (?, ?)",
        [
            ("ath_4", "result_5"),
        ],
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("result_5", "event_4", 8, "bucharest", 2024, "Matei, Vlad", "open"),
        ],
    )

    races = reporting_client_with_db.search_athlete_races("Vlad Matei")
    assert len(races) == 1
    assert races.iloc[0]["name"] == "Matei, Vlad"


def test_search_athlete_races_doubles_partner_match(reporting_client_with_db):
    """Includes doubles races with the athlete as a partner."""
    con = reporting_client_with_db._ensure_connection()
    con.executemany(
        "INSERT INTO athlete_index VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                "ath_5",
                "luke damen, james ingham",
                "luke damen, james ingham",
                "M",
                "GB",
                1,
            ),
            (
                "ath_6",
                "luke ingham, james cunningham",
                "luke ingham, james cunningham",
                "M",
                "GB",
                1,
            ),
        ],
    )
    con.executemany(
        "INSERT INTO athlete_results VALUES (?, ?)",
        [
            ("ath_5", "result_6"),
            ("ath_6", "result_7"),
        ],
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "result_6",
                "event_5",
                8,
                "glasgow",
                2024,
                "Luke Damen, James Ingham",
                "doubles",
            ),
            (
                "result_7",
                "event_6",
                8,
                "glasgow",
                2024,
                "Luke Ingham, James Cunningham",
                "pro_doubles",
            ),
        ],
    )

    races = reporting_client_with_db.search_athlete_races(
        "James Ingham",
        require_unique=False,
    )
    event_ids = set(races["event_id"])
    assert "event_5" in event_ids
    assert "event_6" not in event_ids


def test_search_athlete_races_filters_by_division(reporting_client_with_db):
    """Filters results by the requested division."""
    open_races = reporting_client_with_db.search_athlete_races(
        athlete_name="James Ingham",
        division="open",
    )
    assert len(open_races) == 1
    assert open_races["division"].iloc[0] == "open"
    pro_races = reporting_client_with_db.search_athlete_races(
        athlete_name="James Ingham",
        division="pro",
    )
    assert len(pro_races) == 1
    assert pro_races["division"].iloc[0] == "pro"
