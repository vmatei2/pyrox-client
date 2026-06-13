"""MCP server for the Pyrox reporting service.

Registers the intent-shaped tools from ``mcp_tools`` with a FastMCP server and
mounts it as a streamable-HTTP app at ``/mcp`` on the existing FastAPI app, so
the REST API and the MCP endpoint ship in a single deploy (see ADR-0001).

Serve the composed app with::

    uvicorn pyrox_api_service.mcp_app:app
"""

from __future__ import annotations

import contextlib
import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from pyrox_api_service import mcp_tools
from pyrox_api_service.app import app
from pyrox_api_service.ratelimit import RateLimitMiddleware


def _split_env(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


# DNS-rebinding protection validates Host/Origin headers (it matters mainly for
# localhost-bound servers a browser could reach). The reporting data is public
# and the service sits behind Fly's HTTPS proxy, so protection is off by default
# and auto-enabled only when an operator supplies an allow-list, e.g.
# PYROX_MCP_ALLOWED_HOSTS="pyrox-api.fly.dev".
_allowed_hosts = _split_env("PYROX_MCP_ALLOWED_HOSTS")
_allowed_origins = _split_env("PYROX_MCP_ALLOWED_ORIGINS")
_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=bool(_allowed_hosts),
    allowed_hosts=_allowed_hosts,
    allowed_origins=_allowed_origins,
)

# Stateless HTTP: every request is self-contained, which keeps the server
# restart-safe and friendly to multiple workers. No per-user session state.
# streamable_http_path="/" so that mounting the sub-app at "/mcp" (below)
# exposes the endpoint at "/mcp" rather than "/mcp/mcp".
mcp_server = FastMCP(
    name="pyrox",
    stateless_http=True,
    streamable_http_path="/",
    transport_security=_transport_security,
)

# Each tool's input schema and description are derived from the function's type
# hints and docstring, so registering the functions directly avoids duplication.
TOOLS = (
    mcp_tools.list_filters,
    mcp_tools.find_athlete,
    mcp_tools.get_distribution,
    mcp_tools.get_rankings,
    mcp_tools.get_race_report,
    mcp_tools.get_deepdive,
    mcp_tools.get_athlete_profile,
)
for _tool in TOOLS:
    mcp_server.tool()(_tool)


@contextlib.asynccontextmanager
async def _lifespan(_app):
    """Run the MCP session manager for the lifetime of the FastAPI app."""
    async with mcp_server.session_manager.run():
        yield


app.router.lifespan_context = _lifespan

# Rate limit external MCP callers at this boundary. The REST limiter cannot see
# them: the MCP tools reach the REST app in-process (no Fly-Client-IP header),
# which the limiter intentionally exempts. The same shared limiter is used, so a
# client's MCP and REST calls count against one per-IP window.
mcp_sub = mcp_server.streamable_http_app()
mcp_sub.add_middleware(RateLimitMiddleware)
app.mount("/mcp", mcp_sub)
