"""
Minimal tests for the pyrox client library.

These tests are intentionally simple and heavily commented so you can follow
what is being checked. They avoid real network calls by focusing on module
structure and basic function contracts.
"""
import importlib
import tempfile
import threading
import time
from pathlib import Path
from types import MethodType
from typing import List
from unittest.mock import patch

import pandas as pd
import pytest

try:  # pragma: no cover - exercised only when respx missing locally
    import respx
except ModuleNotFoundError:
    class _RespxStub:
        @staticmethod
        def mock(func=None, **_):
            if func is None:
                def decorator(inner):
                    return inner

                return decorator
            return func


    respx = _RespxStub()
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
        # athlete that is not in the race
        missing = client.get_athlete_in_race(season=5, athlete_name='missing', location='london')
        assert len(missing) == 0


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


@respx.mock
def test_list_races(client):
    manifest_rows = [
        {"season": 7, "location": "Liverpool", "path": "some_s3_path"},
        {"season": 7, "location": "London", "path": "some_s3_path_2024", "year": 2024},
        {"season": 7, "location": "London", "path": "some_s3_path", "year": 2025},
        {"season": 7, "location": "Manchester", "path": "some_s3_path"},
        {"season": 6, "location": "Cardiff", "path": "some_s3_path"}
    ]
    with patch.object(client, "_get_manifest", return_value=pd.DataFrame(manifest_rows)):
        df = client.list_races(season=6)
        expected = pd.DataFrame({"season": [6], "location": ["Cardiff"]})
        #  assert the manifest has been filtered to only return the specified season
        assert_frame_equal(df, expected)


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
