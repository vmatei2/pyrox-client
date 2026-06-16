from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from mcp.types import CallToolResult, TextContent

from scripts import smoke_mcp


def _tools(*names: str):
    return SimpleNamespace(tools=[SimpleNamespace(name=name) for name in names])


def _tool_result(payload: dict) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))],
    )


def test_normalize_mcp_url_adds_trailing_slash():
    assert smoke_mcp.normalize_mcp_url("https://pyrox-api.fly.dev/mcp") == (
        "https://pyrox-api.fly.dev/mcp/"
    )


def test_normalize_mcp_url_rejects_empty_value():
    with pytest.raises(smoke_mcp.McpSmokeError, match="empty"):
        smoke_mcp.normalize_mcp_url("  ")


def test_validate_tool_names_requires_exact_public_tool_set():
    result = _tools(*sorted(smoke_mcp.EXPECTED_TOOL_NAMES - {"get_rankings"}), "debug")

    with pytest.raises(smoke_mcp.McpSmokeError, match="missing"):
        smoke_mcp._validate_tool_names(result)


def test_extract_tool_payload_reads_json_text_content():
    payload = smoke_mcp._extract_tool_payload(
        _tool_result({"seasons": [8], "divisions": ["open"]})
    )

    assert payload == {"seasons": [8], "divisions": ["open"]}


def test_validate_filter_payload_requires_non_empty_filter_lists():
    with pytest.raises(smoke_mcp.McpSmokeError, match="locations"):
        smoke_mcp._validate_filter_payload(
            {
                "seasons": [8],
                "divisions": ["open"],
                "genders": ["F"],
                "locations": [],
            }
        )


def test_smoke_mcp_server_validates_tools_and_filters(monkeypatch):
    async def fake_fetch(url: str, *, timeout_seconds: float):
        assert url == "https://example.test/mcp/"
        assert timeout_seconds == 3.0
        initialize = SimpleNamespace(
            protocolVersion="2025-06-18",
            serverInfo=SimpleNamespace(name="pyrox"),
        )
        filters = _tool_result(
            {
                "seasons": [8, 7],
                "divisions": ["open", "pro"],
                "genders": ["F", "M"],
                "locations": ["london"],
            }
        )
        return initialize, _tools(*smoke_mcp.EXPECTED_TOOL_NAMES), filters

    monkeypatch.setattr(smoke_mcp, "_fetch_mcp_state", fake_fetch)

    report = asyncio.run(
        smoke_mcp.smoke_mcp_server("https://example.test/mcp", timeout_seconds=3.0)
    )

    assert report.url == "https://example.test/mcp/"
    assert report.server_name == "pyrox"
    assert report.tool_names == tuple(sorted(smoke_mcp.EXPECTED_TOOL_NAMES))
    assert report.seasons_count == 2
    assert report.locations_count == 1
