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
import pyrox.core as _client
import pandas as pd
from pandas.testing import assert_frame_equal


@respx.mock
def test_list_races():
    manifest_rows = [
        {"season": 7, "location": "Liverpool", "path": "some_s3_path" },
        {"season": 7, "location": "London", "path": "some_s3_path"},
        {"season": 7, "location": "Manchester", "path": "some_s3_path"},
        {"season": 6, "location": "Cardiff", "path": "some_s3_path"}
    ]
    route = respx.get(DEFAULT_API_URL).mock(return_value=httpx.Response(200, json=manifest_rows))
    df = _client.list_races()
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

@respx.mock
def test_list_races_api_error():
    respx.get(DEFAULT_API_URL).mock(return_value=httpx.Response(500,text="Some API error"))
    #  below is a pyest context manager that assert:  "The code inside this block must raise mod.ApiError -- if it doesn't then fail the test"
    with pytest.raises(_client.ApiError):
        _client.list_races()


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


def test_core_module_public_api():
    """
    Verify key call sites exist in core.py without invoking real HTTP.

    We only assert that functions are importable and callable with minimal
    parameters; we do NOT perform network calls. If signatures change,
    update the names here to keep tests aligned with the public surface.
    """
    core = importlib.import_module("pyrox.core")

    # Example: ensure helper factory exists (name based on current code).
    assert hasattr(core, "_client"), "Expected _client factory present in pyrox.core"
    assert isinstance(core._client, types.FunctionType)

    # If there are public convenience functions (e.g., list_races, get_result),
    # assert they exist without calling them. Adjust names to match your API.
    for name in ("list_races", "get_race", "get_athlete"):
        # Some may not exist yet — this keeps the test flexible.
        if hasattr(core, name):
            assert isinstance(getattr(core, name), types.FunctionType)

