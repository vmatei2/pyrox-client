"""
Simple set of unit tests
for the core PyroxClient functionality.

Using sample_race_data fixutre to avoid hitting live data/CDN.
"""
import importlib
import tempfile
import threading
import time
from pathlib import Path
from types import MethodType
from typing import List
from unittest.mock import patch
from src.pyrox.errors import AthleteNotFound, RaceNotFound

import pandas as pd
import pytest


from pandas.testing import assert_frame_equal

from src.pyrox import PyroxClient
from src.pyrox.core import CacheManager, mmss_to_minutes


@pytest.fixture
def mock_cache_dir():
    """Create a temporary directory for cache testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # using yield as it keeps the temporary directory alive during the test, then cleans it up afterwards
        yield Path(tmpdir)


@pytest.fixture
def client(mock_cache_dir):
    return PyroxClient(cache_dir=mock_cache_dir)


@pytest.fixture
def sample_race_data():
    """Sample race data for testing"""
    return pd.DataFrame([
        {'name': 'Alex Atherton', 'gender': 'M', 'division': 'pro', 'total_time': '00:54:30'},
        {'name': 'Blake Brown', 'gender': 'M', 'division': 'open', 'total_time': '00:56:30'},
        {'name': 'Casey Clark', 'gender': 'F', 'division': 'pro', 'total_time': '01:02:00'}
    ])


def test_get_race_from_cache_when_refresh(client, sample_race_data):
    """Test that get race returns cached data when the cache is fresh"""
    cache_key = "race_5_London_all_all_all"
    client.cache.store(cache_key, sample_race_data)

    #  Moch cache isFresh to return true
    with patch.object(client.cache, "is_fresh", return_value=True):
        with patch.object(client.cache, "load", return_value=sample_race_data):
            result = client.get_race(season=5, location="London")

    #  asert we get returned what we expected
    pd.testing.assert_frame_equal(result, sample_race_data)


def test_get_race_from_s3_when_not_cache(client, sample_race_data):
    with patch.object(client.cache, "is_fresh", return_value=False):
        with patch.object(client, "_get_race_from_cdn", return_value=sample_race_data):
            result = client.get_race(season=5, location="London")

    #  asert we get returned what we expected
    expected = sample_race_data.copy().reset_index(drop=True)
    expected["total_time"] = mmss_to_minutes(expected["total_time"])
    assert_frame_equal(result, expected)


def test_get_athlete_in_race(client, sample_race_data):
    """Test that athlete specific searching works as expected"""
    with patch.object(client, "get_race", return_value=sample_race_data):
        user = client.get_athlete_in_race(season=5, athlete_name='atherton', location='London')
        assert list(user['name']) == ['Alex Atherton']
        # athlete that is *not* in the race -> should raise
        with pytest.raises(AthleteNotFound):
            client.get_athlete_in_race(
                season=5,
                athlete_name="missing",
                location="london",
            )

def test_get_race_filters_total_time_lt(client, sample_race_data):
    with patch.object(client.cache, "is_fresh", return_value=False):
        with patch.object(client, "_get_race_from_cdn", return_value=sample_race_data):
            result = client.get_race(season=5, location="London", total_time=60)

    assert result["name"].tolist() == ["Alex Atherton", "Blake Brown"]
    assert (result["total_time"] < 60).all()
    #  ensure the total time returned is of the expected type!
    assert (result["total_time"].dtype == float)


def test_get_race_filters_total_time_range(client, sample_race_data):
    with patch.object(client.cache, "is_fresh", return_value=False):
        with patch.object(client, "_get_race_from_cdn", return_value=sample_race_data):
            result = client.get_race(season=5, location="London", total_time=(55, 60))

    assert result["name"].tolist() == ["Blake Brown"]
    assert (result["total_time"] > 55).all()
    assert (result["total_time"] < 60).all()


def test_cdn_url_from_manifest(client):
    manifest_rows = [
        {"season": 7, "location": "Liverpool", "path": "some_s3_path_liverpool"},
        {"season": 7, "location": "London", "path": "some_s3_path_2024", "year": 2024},
        {"season": 7, "location": "London", "path": "some_s3_path_2025", "year": 2025},
        {"season": 7, "location": "Manchester", "path": "some_s3_path"},
        {"season": 6, "location": "Cardiff", "path": "some_s3_path"}
    ]
    with patch.object(client, "_get_manifest", return_value=pd.DataFrame(manifest_rows)):
        path_2025 = client._cdn_url_from_manifest(season=7, location="London", year=2025)

        assert (path_2025 == client._join_cdn("some_s3_path_2025"))
        path_2024 = client._cdn_url_from_manifest(season=7, location="london", year=2024)
        assert (path_2024 == client._join_cdn("some_s3_path_2024"))
        path_liverpool = client._cdn_url_from_manifest(season=7, location="liverpool")
        assert (path_liverpool == client._join_cdn("some_s3_path_liverpool"))


def test_list_races(client):
    manifest_rows = [
        {
            "season": 7,
            "location": "Liverpool",
            "path": "some_s3_path",
            "file_last_modified": "2025-02-01",
        },
        {
            "season": 7,
            "location": "London",
            "path": "some_s3_path_2024",
            "year": 2024,
            "file_last_modified": "2024-10-01",
        },
        {
            "season": 7,
            "location": "London",
            "path": "some_s3_path",
            "year": 2025,
            "file_last_modified": "2025-01-15",
        },
        {
            "season": 7,
            "location": "Manchester",
            "path": "some_s3_path",
            "file_last_modified": "2025-03-10",
        },
        {
            "season": 6,
            "location": "Cardiff",
            "path": "some_s3_path",
            "file_last_modified": "2024-08-20",
        },
    ]
    with patch.object(client, "_get_manifest", return_value=pd.DataFrame(manifest_rows)):
        df = client.list_races(season=6)
        expected = pd.DataFrame(
            {"season": [6], "location": ["Cardiff"], "file_last_modified": ["2024-08-20"]}
        )
        #  assert the manifest has been filtered to only return the specified season
        assert_frame_equal(df, expected)


def test_manifest_discovery_helpers_return_sorted_values(client):
    manifest_rows = [
        {"season": 8, "location": "London", "year": 2026, "path": "london-2026"},
        {"season": 7, "location": "Berlin", "year": 2025, "path": "berlin-2025"},
        {"season": 8, "location": "london", "year": 2025, "path": "london-2025"},
        {"season": 8, "location": "Manchester", "year": None, "path": "manchester"},
        {"season": None, "location": None, "year": None, "path": "missing"},
    ]
    with patch.object(client, "_get_manifest", return_value=pd.DataFrame(manifest_rows)):
        assert client.list_seasons() == [7, 8]
        assert client.list_locations(season=8) == ["London", "Manchester"]
        assert client.list_locations(season=999) == []
        assert client.list_years(season=8, location="LONDON") == [2025, 2026]
        assert client.list_years(season=999, location="london") == []


def test_manifest_discovery_helpers_pass_force_refresh(client):
    with patch.object(
        client,
        "_get_manifest",
        return_value=pd.DataFrame([{"season": 8, "location": "London", "year": 2026}]),
    ) as get_manifest:
        assert client.list_seasons(force_refresh=True) == [8]
        get_manifest.assert_called_with(force_refresh=True)


def test_manifest_row_missing_season_raises_enriched_race_not_found(client):
    manifest_rows = [
        {"season": 7, "location": "London", "year": 2025, "path": "london"},
        {"season": 8, "location": "Berlin", "year": 2026, "path": "berlin"},
    ]
    with patch.object(client, "_get_manifest", return_value=pd.DataFrame(manifest_rows)):
        with pytest.raises(RaceNotFound) as exc_info:
            client._manifest_row(season=9, location="London")

    exc = exc_info.value
    assert exc.season == 9
    assert exc.location == "London"
    assert exc.available_seasons == [7, 8]
    assert exc.suggestions == []
    assert "Available seasons" in str(exc)


def test_manifest_row_misspelled_location_suggests_close_match(client):
    manifest_rows = [
        {"season": 8, "location": "london", "year": 2025, "path": "london"},
        {"season": 8, "location": "manchester", "year": 2025, "path": "manchester"},
    ]
    with patch.object(client, "_get_manifest", return_value=pd.DataFrame(manifest_rows)):
        with pytest.raises(RaceNotFound) as exc_info:
            client._manifest_row(season=8, location="londn")

    exc = exc_info.value
    assert exc.season == 8
    assert exc.location == "londn"
    assert exc.available_locations == ["london", "manchester"]
    assert exc.suggestions == ["london"]
    assert "Did you mean" in str(exc)


def test_manifest_row_wrong_year_lists_available_years(client):
    manifest_rows = [
        {"season": 8, "location": "london", "year": 2025, "path": "london-2025"},
        {"season": 8, "location": "london", "year": 2026, "path": "london-2026"},
    ]
    with patch.object(client, "_get_manifest", return_value=pd.DataFrame(manifest_rows)):
        with pytest.raises(RaceNotFound) as exc_info:
            client._manifest_row(season=8, location="London", year=2024)

    exc = exc_info.value
    assert exc.season == 8
    assert exc.location == "London"
    assert exc.year == 2024
    assert exc.available_years == [2025, 2026]
    assert "Available years" in str(exc)


def test_cache_manager_store_thread_safety(tmp_path):
    cache = CacheManager(cache_dir=tmp_path)
    df = pd.DataFrame({"value": [1]})

    started = threading.Event()
    continue_event = threading.Event()
    original_write = cache._write_metadata_locked

    def patched_write_metadata(self):
        first_iteration = True
        for _ in self.metadata:
            if first_iteration:
                first_iteration = False
                started.set()
                assert continue_event.wait(timeout=1), "timed out while waiting to simulate concurrent write"
        original_write()

    cache._write_metadata_locked = MethodType(patched_write_metadata, cache)

    errors: List[Exception] = []

    def store_key(name: str) -> None:
        try:
            cache.store(name, df)
        except Exception as exc:  # pragma: no cover - failure path assertion below
            errors.append(exc)

    first = threading.Thread(target=store_key, args=("alpha",))
    first.start()
    assert started.wait(timeout=1), "cache did not begin writing metadata in time"

    second = threading.Thread(target=store_key, args=("bravo",))
    second.start()
    time.sleep(0.05)
    continue_event.set()

    first.join(timeout=1)
    second.join(timeout=1)

    assert not first.is_alive() and not second.is_alive(), "store threads failed to finish"
    assert not errors, f"unexpected cache errors: {errors}"
    assert sorted(cache.metadata_snapshot().keys()) == ["alpha", "bravo"]


def test_package_exposes_version():
    """
    Ensure the installed package exposes a __version__ attribute.

    Rationale: Many tools and users rely on a package-level version for
    debugging and reproducibility. If not available, feel free to adjust
    this assertion to your preferred metadata surface.
    """
    pkg = importlib.import_module("pyrox")
    # We expect a string-like version.
    assert hasattr(pkg, "__version__"), "pyrox.__version__ should exist"
    assert isinstance(pkg.__version__, str) and pkg.__version__, "__version__ should be non-empty"
