"""Edge rate limiting for the reporting service.

A per-client-IP limiter applied once, as middleware on the composed app. The
composed app mounts ``/mcp`` under the same FastAPI app the REST routes live on,
so a single middleware on that app already wraps *both* the REST endpoints and
the mounted MCP sub-app — there must be exactly one limiter, on the parent app.
Adding it to the sub-app too would double-count every MCP request.

Each reporting call runs a DuckDB scan, so an unbounded caller (a runaway agent
loop against the public ``/mcp`` endpoint, for example) is the main cost/DoS
exposure while the service is open.

Keying and the internal exemption:
    Fly's proxy adds a ``Fly-Client-IP`` header to inbound requests. Requests
    *without* that header are not edge traffic — they are the in-process ASGI
    calls the MCP tools make into the REST app (``mcp_tools`` holds a
    ``TestClient(app)``) and the test suite's TestClient calls. Those are skipped
    so internal calls are never throttled against a shared key.

Counting once, never on a redirect:
    The mounted MCP endpoint serves at ``/mcp/`` and Starlette answers ``/mcp``
    with a ``307`` to it, which clients follow — so one logical MCP call arrives
    as two HTTP requests. We gate with the non-consuming ``test()`` and only
    ``hit()`` (consume a slot) once we see a non-3xx response, so the redirect
    hop costs nothing and each served request counts exactly once.

Implementation note:
    Uses the ``limits`` library (the engine ``slowapi`` is built on) behind a
    small pure-ASGI middleware rather than ``slowapi``'s ``SlowAPIMiddleware``.
    That middleware is route-endpoint coupled (unreliable on a mounted ASGI
    sub-app) and raises ``AttributeError`` on the request-exempt path we need.
    Pure ASGI also forwards allowed requests untouched, so it does not buffer the
    MCP transport's streaming responses.
"""

from __future__ import annotations

import os

from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from starlette.responses import JSONResponse

FLY_CLIENT_IP_HEADER = b"fly-client-ip"
DEFAULT_RATE = "60/minute"
_NAMESPACE = "pyrox"

_rate = parse(os.getenv("PYROX_RATE_LIMIT", DEFAULT_RATE))
_limiter = MovingWindowRateLimiter(MemoryStorage())


class RateLimitMiddleware:
    """Reject edge requests that exceed the per-client-IP rate.

    Edge requests carry a ``Fly-Client-IP`` header; requests without it are
    in-process ASGI calls or tests and pass through unlimited (see module
    docstring). Pure ASGI: allowed requests are forwarded untouched, and a slot
    is consumed only on a non-redirect response so each served request counts
    once.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client_ip = dict(scope["headers"]).get(FLY_CLIENT_IP_HEADER)
        if not client_ip:
            await self.app(scope, receive, send)
            return

        identity = client_ip.decode()
        if not _limiter.test(_rate, _NAMESPACE, identity):
            response = JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
            await response(scope, receive, send)
            return

        consumed = False

        async def send_wrapper(message):
            nonlocal consumed
            if message["type"] == "http.response.start" and not consumed:
                consumed = True
                # Don't charge the /mcp -> /mcp/ 307 hop; charge the real response.
                if not 300 <= message["status"] < 400:
                    _limiter.hit(_rate, _NAMESPACE, identity)
            await send(message)

        await self.app(scope, receive, send_wrapper)
