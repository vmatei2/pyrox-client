"""Tests for the edge rate-limit middleware.

The middleware keys off the ``Fly-Client-IP`` header that Fly's proxy adds to
inbound requests. Requests without that header are in-process ASGI calls (the
MCP tools call the REST app via TestClient) or tests, and must never be
throttled. These tests pin a low limit via monkeypatch so the window is cheap to
exhaust, then drive a standalone app through the real middleware.
"""

import pytest

pytest.importorskip("limits")

from limits import parse  # noqa: E402
from limits.storage import MemoryStorage  # noqa: E402
from limits.strategies import MovingWindowRateLimiter  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.responses import PlainTextResponse  # noqa: E402
from starlette.routing import Route  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from pyrox_api_service import ratelimit  # noqa: E402
from pyrox_api_service.ratelimit import RateLimitMiddleware  # noqa: E402


def _low_limit(monkeypatch, rate: str = "2/minute") -> None:
    """Pin a small, fresh limiter so a few requests exhaust the window."""
    monkeypatch.setattr(ratelimit, "_rate", parse(rate))
    monkeypatch.setattr(ratelimit, "_limiter", MovingWindowRateLimiter(MemoryStorage()))


def _client() -> TestClient:
    async def ok(request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/x", ok)])
    app.add_middleware(RateLimitMiddleware)
    return TestClient(app)


def test_edge_requests_are_limited(monkeypatch):
    _low_limit(monkeypatch)
    client = _client()
    headers = {"fly-client-ip": "1.2.3.4"}
    codes = [client.get("/x", headers=headers).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_requests_without_fly_header_are_never_limited(monkeypatch):
    _low_limit(monkeypatch)
    client = _client()
    # No Fly-Client-IP -> in-process/internal shape -> exempt, even past the limit.
    codes = [client.get("/x").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 200, 200]


def test_limit_is_isolated_per_client_ip(monkeypatch):
    _low_limit(monkeypatch)
    client = _client()
    first = {"fly-client-ip": "1.1.1.1"}
    assert client.get("/x", headers=first).status_code == 200
    assert client.get("/x", headers=first).status_code == 200
    assert client.get("/x", headers=first).status_code == 429
    # A different client IP has its own window.
    assert client.get("/x", headers={"fly-client-ip": "2.2.2.2"}).status_code == 200


def test_mounted_path_with_redirect_counts_once(monkeypatch):
    """A mounted endpoint (like /mcp) that 307-redirects to its trailing-slash
    form must consume exactly one slot per logical call, not two.

    This guards against two regressions: adding the middleware to the sub-app as
    well as the parent (double count), and charging the redirect hop. The parent
    app's single middleware must cover the mount, and the 307 must be free.
    """
    from fastapi import FastAPI
    from starlette.routing import Route as _Route

    _low_limit(monkeypatch, "2/minute")

    async def leaf(request):
        return PlainTextResponse("leaf")

    sub = Starlette(routes=[_Route("/", leaf)])
    parent = FastAPI()
    parent.add_middleware(RateLimitMiddleware)  # only on the parent, as in production
    parent.mount("/sub", sub)

    client = TestClient(parent)  # follows the /sub -> /sub/ 307
    headers = {"fly-client-ip": "1.2.3.4"}
    # With single-counting: two calls fit a 2/minute window, the third is denied.
    codes = [client.get("/sub", headers=headers).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
