import matplotlib
import pandas as pd
import pytest

from src.pyrox.errors import AthleteNotFound
from src.pyrox.reporting import ReportingClient

matplotlib.use("Agg")

@pytest.fixture
def reporting_client_with_db():
    reporting = ReportingClient(client=object(), database=":memory:")
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


@pytest.fixture
def reporting_client_with_report_tables():
    reporting = ReportingClient(client=object(), database=":memory:")
    con = reporting._ensure_connection()
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
            event_id VARCHAR,
            location VARCHAR,
            division VARCHAR,
            gender VARCHAR,
            age_group VARCHAR,
            split_name VARCHAR,
            split_time_min DOUBLE,
            split_rank INTEGER,
            split_size INTEGER,
            split_percentile DOUBLE
        );
        """
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("r1", "event_1", 8, "london", 2024, "open", "M", "30-34", "A One", 60.0),
            ("r2", "event_1", 8, "london", 2024, "open", "M", "30-34", "B Two", 70.0),
            ("r3", "event_1", 8, "london", 2024, "pro", "M", "30-34", "C Three", 65.0),
            ("r4", "event_2", 8, "london", 2024, "open", "M", "30-34", "D Four", 66.0),
        ],
    )
    con.executemany(
        "INSERT INTO race_rankings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("r1", 1, 2, 1.0, 1, 3, 1.0, 1, 3, 1.0),
            ("r2", 2, 2, 0.0, 3, 3, 0.0, 3, 3, 0.0),
            ("r3", 1, 1, 1.0, 2, 3, 0.5, 2, 3, 0.5),
            ("r4", 1, 1, 1.0, 2, 4, 0.5, 2, 4, 0.5),
        ],
    )
    con.executemany(
        "INSERT INTO split_percentiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("r1", "event_1", "london", "open", "M", "30-34", "run_1", 5.0, 1, 2, 1.0),
            ("r1", "event_1", "london", "open", "M", "30-34", "ski_erg", 3.0, 1, 2, 1.0),
            ("r2", "event_1", "london", "open", "M", "30-34", "run_1", 6.0, 2, 2, 0.0),
            ("r2", "event_1", "london", "open", "M", "30-34", "ski_erg", 4.0, 2, 2, 0.0),
            ("r3", "event_1", "london", "pro", "M", "30-34", "run_1", 5.5, 1, 1, 1.0),
            ("r4", "event_2", "london", "open", "M", "30-34", "run_1", 5.2, 1, 3, 0.8),
        ],
    )
    return reporting


def test_race_report_returns_expected_data(reporting_client_with_report_tables):
    report = reporting_client_with_report_tables.race_report("r1")

    race = report["race"]
    assert len(race) == 1
    assert race.iloc[0]["result_id"] == "r1"
    assert race.iloc[0]["event_percentile"] == pytest.approx(1.0)

    cohort = report["cohort"]
    assert set(cohort["result_id"]) == {"r1", "r2", "r4"}
    assert set(cohort["event_id"]) == {"event_1", "event_2"}

    splits = report["splits"]
    assert splits["split_name"].tolist() == ["run_1", "ski_erg"]
    assert splits["split_percentile"].tolist() == pytest.approx([1.0, 1.0])
    assert splits["split_percentile_time_window"].tolist() == pytest.approx([1.0, 1.0])

    cohort_splits = report["cohort_splits"]
    assert set(cohort_splits["result_id"]) == {"r1", "r2", "r4"}
    assert set(cohort_splits["split_name"]) == {"run_1", "ski_erg"}

    time_window = report["cohort_time_window"]
    assert set(time_window["result_id"]) == {"r1", "r3"}
    assert set(time_window["event_id"]) == {"event_1"}

    time_window_splits = report["cohort_time_window_splits"]
    assert set(time_window_splits["result_id"]) == {"r1", "r3"}
    assert set(time_window_splits["split_name"]) == {"run_1", "ski_erg"}


def test_race_report_missing_result_id_raises(reporting_client_with_report_tables):
    with pytest.raises(ValueError):
        reporting_client_with_report_tables.race_report("missing")


@pytest.fixture
def reporting_client_with_plot_data():
    reporting = ReportingClient(client=object(), database=":memory:")
    con = reporting._ensure_connection()
    con.execute(
        """
        CREATE TABLE race_results (
            result_id VARCHAR,
            season INTEGER,
            location VARCHAR,
            division VARCHAR,
            gender VARCHAR,
            age_group VARCHAR,
            total_time_min DOUBLE,
            run1_time_min DOUBLE,
            sledPush_time_min DOUBLE
        );
        """
    )
    con.executemany(
        "INSERT INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("r1", 8, "london", "open", "M", "25-29", 60.0, 5.0, 3.0),
            ("r2", 8, "london", "open", "M", "25-29", 64.0, 6.0, 4.0),
            ("r3", 8, "london", "open", "M", "25-29", 70.0, 7.0, 5.0),
            ("r4", 8, "paris", "open", "M", "25-29", 62.0, 4.5, 2.5),
        ],
    )
    return reporting


def test_plot_cohort_distribution_uses_location_cohort(reporting_client_with_plot_data):
    fig, ax = reporting_client_with_plot_data.plot_cohort_distribution("r1", "run1")

    assert "run1_time_min distribution" in ax.get_title()
    assert len(ax.lines) == 1
    assert list(ax.lines[0].get_xdata()) == [5.0, 5.0]
    fig.clear()


def test_plot_cohort_distribution_resolves_metric_alias(reporting_client_with_plot_data):
    fig, ax = reporting_client_with_plot_data.plot_cohort_distribution("r1", "sledPush")

    assert "sledPush_time_min" in ax.get_title()
    assert list(ax.lines[0].get_xdata()) == [3.0, 3.0]
    fig.clear()


def test_plot_cohort_distribution_time_window(reporting_client_with_plot_data):
    fig, ax = reporting_client_with_plot_data.plot_cohort_distribution(
        "r1",
        "run1",
        cohort_mode="time_window",
        cohort_time_window_min=5.0,
    )

    assert "season 8" in ax.get_title()
    assert sum(patch.get_height() for patch in ax.patches) == pytest.approx(2.0)
    fig.clear()
