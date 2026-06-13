"""Edge rate limiting for the reporting service.

A per-client-IP limiter applied at the two external entry points: the REST app
and the mounted MCP sub-app. Each reporting call runs a DuckDB scan, so an
unbounded caller (a runaway agent loop against the public ``/mcp`` endpoint, for
example) is the main cost/DoS exposure while the service is open.

Keying and the internal exemption:
    Fly's proxy adds a ``Fly-Client-IP`` header to inbound requests. Requests
    *without* that header are not edge traffic — they are the in-process ASGI
    calls the MCP tools make into the REST app (``mcp_tools`` holds a
    ``TestClient(app)``) and the test suite's TestClient calls. Those are skipped
    so internal calls are never throttled against a shared key (which would both
    429 MCP tool bursts against each other and break the in-process tests).

Implementation note:
    This uses the ``limits`` library (the engine ``slowapi`` is built on) behind
    a small pure-ASGI middleware rather than ``slowapi``'s ``SlowAPIMiddleware``.
    That middleware is route-endpoint coupled (unreliable on a mounted ASGI
    sub-app) and raises ``AttributeError`` on the request-exempt path we need.
    A pure-ASGI middleware also passes allowed requests through untouched, so it
    does not buffer the MCP transport's streaming responses.
"""

from __future__ import annotations

import os

from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from starlette.responses import JSONResponse

FLY_CLIENT_IP_HEADER = b"fly-client-ip"
DEFAULT_RATE = "60/minute"

# One shared limiter/storage instance: imported by both the REST app and the MCP
# sub-app so a client's REST and MCP calls count against the same per-IP window.
_rate = parse(os.getenv("PYROX_RATE_LIMIT", DEFAULT_RATE))
_limiter = MovingWindowRateLimiter(MemoryStorage())


class RateLimitMiddleware:
    """Reject edge requests that exceed the per-client-IP rate.

    Edge requests carry a ``Fly-Client-IP`` header; requests without it are
    in-process ASGI calls or tests and pass through unlimited (see module
    docstring). Pure ASGI so allowed requests are forwarded untouched.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            client_ip = dict(scope["headers"]).get(FLY_CLIENT_IP_HEADER)
            if client_ip and not _limiter.hit(_rate, "pyrox", client_ip.decode()):
                response = JSONResponse(
                    {"detail": "rate limit exceeded"}, status_code=429
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
