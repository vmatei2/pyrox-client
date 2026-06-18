from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any, Sequence, cast

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, InitializeResult, ListToolsResult

DEFAULT_MCP_URL = "https://pyrox-api.fly.dev/mcp/"
DEFAULT_TIMEOUT_SECONDS = 20.0
EXPECTED_TOOL_NAMES = frozenset(
    {
        "list_filters",
        "list_races",
        "find_athlete",
        "get_distribution",
        "get_race_summary",
        "get_cohort_segment_averages",
        "get_rankings",
        "get_race_report",
        "get_deepdive",
        "get_athlete_profile",
    }
)


class McpSmokeError(RuntimeError):
    """Raised when the live MCP smoke test finds an unhealthy connector."""


@dataclass(frozen=True)
class McpSmokeReport:
    url: str
    protocol_version: str | None
    server_name: str | None
    tool_names: tuple[str, ...]
    seasons_count: int
    divisions_count: int
    genders_count: int
    locations_count: int


def normalize_mcp_url(value: str) -> str:
    """Normalize the streamable-HTTP MCP endpoint URL used by public docs."""
    url = value.strip()
    if not url:
        raise McpSmokeError("MCP URL is empty.")
    if "?" in url or "#" in url:
        return url
    return url.rstrip("/") + "/"


def _validate_tool_names(result: ListToolsResult) -> tuple[str, ...]:
    tool_names = tuple(sorted(tool.name for tool in result.tools))
    actual = set(tool_names)
    missing = EXPECTED_TOOL_NAMES - actual
    extra = actual - EXPECTED_TOOL_NAMES
    if missing or extra:
        raise McpSmokeError(
            "Unexpected MCP tool set: "
            f"missing={sorted(missing)}, extra={sorted(extra)}, actual={tool_names}"
        )
    return tool_names


def _extract_tool_payload(result: CallToolResult) -> dict[str, Any]:
    if result.isError:
        text = _tool_result_text(result)
        raise McpSmokeError(f"Tool call returned MCP error: {text}")

    if result.structuredContent is not None:
        return dict(result.structuredContent)

    text = _tool_result_text(result)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise McpSmokeError(f"Tool result was not JSON: {text[:500]!r}") from exc
    if not isinstance(payload, dict):
        raise McpSmokeError(
            f"Tool result JSON was not an object: {type(payload).__name__}"
        )
    return payload


def _tool_result_text(result: CallToolResult) -> str:
    chunks = []
    for content in result.content:
        text = getattr(content, "text", None)
        if text:
            chunks.append(str(text))
    return "\n".join(chunks).strip()


def _validate_filter_payload(payload: dict[str, Any]) -> tuple[int, int, int, int]:
    if "error" in payload:
        raise McpSmokeError(f"list_filters returned service error: {payload['error']}")

    counts = []
    for key in ("seasons", "divisions", "genders", "locations"):
        value = payload.get(key)
        if not isinstance(value, list) or not value:
            raise McpSmokeError(
                f"list_filters returned empty or invalid {key}: {value!r}"
            )
        counts.append(len(value))
    return cast(tuple[int, int, int, int], tuple(counts))


async def _fetch_mcp_state(
    url: str,
    *,
    timeout_seconds: float,
) -> tuple[InitializeResult, ListToolsResult, CallToolResult]:
    timeout = httpx.Timeout(
        timeout_seconds,
        connect=min(5.0, timeout_seconds),
        write=min(5.0, timeout_seconds),
        pool=min(5.0, timeout_seconds),
    )
    headers = {"user-agent": "pyrox-mcp-smoke/1.0"}
    async with httpx.AsyncClient(
        timeout=timeout, headers=headers, follow_redirects=True
    ) as client:
        async with streamable_http_client(url, http_client=client) as (read, write, _):
            async with ClientSession(
                read,
                write,
                read_timeout_seconds=timedelta(seconds=timeout_seconds),
            ) as session:
                initialize_result = await session.initialize()
                tools_result = await session.list_tools()
                filters_result = await session.call_tool("list_filters", {})
                return initialize_result, tools_result, filters_result


async def smoke_mcp_server(
    url: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> McpSmokeReport:
    normalized_url = normalize_mcp_url(url)
    initialize_result, tools_result, filters_result = await _fetch_mcp_state(
        normalized_url,
        timeout_seconds=timeout_seconds,
    )
    tool_names = _validate_tool_names(tools_result)
    seasons_count, divisions_count, genders_count, locations_count = (
        _validate_filter_payload(_extract_tool_payload(filters_result))
    )
    server_info = initialize_result.serverInfo
    return McpSmokeReport(
        url=normalized_url,
        protocol_version=initialize_result.protocolVersion,
        server_name=getattr(server_info, "name", None),
        tool_names=tool_names,
        seasons_count=seasons_count,
        divisions_count=divisions_count,
        genders_count=genders_count,
        locations_count=locations_count,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke test a Pyrox MCP streamable-HTTP endpoint.",
    )
    parser.add_argument(
        "--url",
        default=os.getenv("PYROX_MCP_URL", DEFAULT_MCP_URL),
        help=f"MCP endpoint URL. Defaults to PYROX_MCP_URL or {DEFAULT_MCP_URL}",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("PYROX_MCP_TIMEOUT", DEFAULT_TIMEOUT_SECONDS)),
        help=f"Per-operation timeout in seconds. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the smoke report as JSON.",
    )
    return parser


def _format_exception(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        messages = [_format_exception(child) for child in exc.exceptions]
        return "; ".join(message for message in messages if message) or str(exc)
    return f"{type(exc).__name__}: {exc}"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = asyncio.run(smoke_mcp_server(args.url, timeout_seconds=args.timeout))
    except Exception as exc:
        print(f"MCP smoke FAILED: {_format_exception(exc)}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
    else:
        print(
            "MCP smoke passed: "
            f"url={report.url} server={report.server_name or 'unknown'} "
            f"tools={len(report.tool_names)} seasons={report.seasons_count} "
            f"divisions={report.divisions_count} genders={report.genders_count} "
            f"locations={report.locations_count}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
