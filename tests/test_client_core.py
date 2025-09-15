"""
Minimal tests for the pyrox client library.

These tests are intentionally simple and heavily commented so you can follow
what is being checked. They avoid real network calls by focusing on module
structure and basic function contracts.
"""

import importlib
import types

import pytest
import respx
import httpx
from pyrox.core import DEFAULT_API_URL
from pyrox.core import PyroxClient
import pandas as pd
from pandas.testing import assert_frame_equal


_client = PyroxClient()

##  TO-DO fix failing unit test here after moving to caching logic / and not just defaulting to API
@respx.mock
def test_list_races():
    manifest_rows = [
        {"season": 7, "location": "Liverpool", "path": "some_s3_path" },
        {"season": 7, "location": "London", "path": "some_s3_path"},
        {"season": 7, "location": "Manchester", "path": "some_s3_path"},
        {"season": 6, "location": "Cardiff", "path": "some_s3_path"}
    ]
    route = respx.get(f"{DEFAULT_API_URL}/v1/manifest").mock(return_value=httpx.Response(200, json=manifest_rows))
    df = _client.list_races(force_refresh=True)
    assert route.called

    expected = (
        pd.DataFrame({"season": [6, 7, 7, 7], "location":["Cardiff", "Liverpool", "London", "Manchester"]})
    )
    #  assert we have had everything returned form the manifest
    assert_frame_equal(df, expected)
    df = _client.list_races(season=6)
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

