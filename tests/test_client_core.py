"""
Minimal tests for the pyrox client library.

These tests are intentionally simple and heavily commented so you can follow
what is being checked. They avoid real network calls by focusing on module
structure and basic function contracts.
"""
import importlib
from unittest.mock import patch

import pytest
import respx
import httpx
from pyrox.core import DEFAULT_API_URL
import tempfile
from pathlib import Path
from pyrox.core import PyroxClient
import pandas as pd
from pandas.testing import assert_frame_equal

@pytest.fixture
def mock_cache_dir():
    """Create a temporary directory for cache testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # using yield as it keeps the temporary directory alive during the test, then cleans it up afterwards
        yield Path(tmpdir)


@pytest.fixture
def client(mock_cache_dir):
    return PyroxClient(DEFAULT_API_URL, cache_dir=mock_cache_dir)

@pytest.fixture
def sample_race_data():
    """Sample race data for testing"""
    return pd.DataFrame([
        {'athlete name': 'John Jono', 'gender': 'M', 'division': 'pro', 'time': '56:00:01'},
        {'athlete name': 'Chris Christian', 'gender': 'M', 'division': 'open', 'time': '59:00:00'}
    ])


def test_get_race_from_cache_when_refresh(client, sample_race_data):
    """Test that get race returns cached data when the cache is fresh"""
    cache_key = "race_2023_london_all_all"
    client.cache.store(cache_key, sample_race_data)

    #  Moch cache isFresh to return true
    with patch.object(client.cache, "is_fresh", return_value=True):
        with patch.object(client.cache, "load", return_value=sample_race_data):
            result = client.get_race(season=5, location="London")

    #  asert we get returned what we expected
    pd.testing.assert_frame_equal(result, sample_race_data)

def test_get_race_from_s3_when_not_cache(client, sample_race_data):

    with patch.object(client.cache, "is_fresh", return_value=False):
        with patch.object(client, "_get_race_from_s3", return_value=sample_race_data):
            result = client.get_race(season=5, location="London")

    #  asert we get returned what we expected
    pd.testing.assert_frame_equal(result, sample_race_data)

@respx.mock
def test_get_race_when_not_cache_nots3(client, sample_race_data):
    route = respx.get(f"{DEFAULT_API_URL}/v1/race/5/london").mock(return_value=httpx.Response(status_code=200, json=sample_race_data.to_dict('records')))
    with patch.object(client.cache, "is_fresh", return_value=False):
        #  note to self -- patching attributes (rather then functions --> do not assign return_value )
        with patch.object(client, "prefer_s3", False):
            result = client.get_race(season=5, location="london")

    assert route.called
    #  asert we get returned what was expected
    pd.testing.assert_frame_equal(result, sample_race_data)



@respx.mock
def test_list_races(client):
    manifest_rows = [
        {"season": 7, "location": "Liverpool", "path": "some_s3_path" },
        {"season": 7, "location": "London", "path": "some_s3_path"},
        {"season": 7, "location": "Manchester", "path": "some_s3_path"},
        {"season": 6, "location": "Cardiff", "path": "some_s3_path"}
    ]
    route = respx.get(f"{DEFAULT_API_URL}/v1/manifest").mock(return_value=httpx.Response(200, json=manifest_rows))
    df = client.list_races(force_refresh=True)
    assert route.called

    expected = (
        pd.DataFrame({"season": [6, 7, 7, 7], "location":["Cardiff", "Liverpool", "London", "Manchester"]})
    )
    #  assert we have had everything returned form the manifest
    assert_frame_equal(df, expected)
    df = client.list_races(season=6)
    expected = pd.DataFrame({"season": [6], "location":["Cardiff"]})
    #  assert the manifest has been filtered to only return the specified season
    assert_frame_equal(df, expected)



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

