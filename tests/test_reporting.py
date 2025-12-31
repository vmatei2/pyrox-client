import pandas as pd

from src.pyrox.reporting import build_athlete_options


def test_build_athlete_options_basic():
    df = pd.DataFrame(
        {
            "name": ["Alex Atherton", "Blake Brown", "Alex Atherton", "  ", None],
            "total_time": [55.2, 56.1, 54.8, 60.0, 52.0],
        }
    )

    options = build_athlete_options(df)

    assert options[0]["value"] == "Alex Atherton"
    assert options[0]["count"] == 2
    assert options[1]["value"] == "Blake Brown"
    assert options[1]["count"] == 1


def test_build_athlete_options_query_and_limit():
    df = pd.DataFrame(
        {
            "name": ["Alice", "Alicia", "Bob", "Bobby", "Bobby"],
        }
    )

    options = build_athlete_options(df, query="ali", limit=1)
    assert len(options) == 1
    assert options[0]["value"] in {"Alice", "Alicia"}
