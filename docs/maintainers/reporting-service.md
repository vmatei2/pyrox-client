# Reporting Service and UI

This repository includes a FastAPI reporting service and a Vite/React UI for
project workflows. This stack is separate from the published `pyrox-client`
package. The PyPI wheel ships only the `pyrox` client library (`src/pyrox`);
`pyrox_api_service/` and `ui/` are not part of it.

## Canonical Backend Module

`pyrox_api_service.app:app` is the pure REST app. To serve the REST API **and**
the mounted MCP server together (the deployed configuration), use the composed
app:

```bash
pyrox_api_service.mcp_app:app
```

There is a compatibility shim at `src/pyrox/api/` for legacy imports, but new
commands should use `pyrox_api_service.app:app` (REST only) or
`pyrox_api_service.mcp_app:app` (REST + MCP).

## MCP Server

`pyrox_api_service/mcp_app.py` mounts a streamable-HTTP MCP server at `/mcp`
on the FastAPI app (single deploy — see `docs/adr/0001-mcp-over-http-reporting-service.md`).
It exposes intent-shaped tools (`list_filters`, `list_races`, `find_athlete`,
`get_distribution`, `get_race_summary`, `get_cohort_segment_averages`,
`get_rankings`, `get_race_report`, `get_deepdive`, `get_athlete_profile`) whose
logic lives in `pyrox_api_service/mcp_tools.py` and calls the REST app in-process.
Add the URL `https://<host>/mcp` as a remote connector in Claude.

The `/mcp` endpoint is currently **open** (no authentication) — it serves the same
public data as the REST API.

Smoke-test the live connector before public launch or after deploy:

```bash
PYROX_MCP_URL=https://pyrox-api.fly.dev/mcp/ uv run python scripts/smoke_mcp.py --json
```

## API Contract: Athlete Profile Percentiles

The athlete profile endpoints (`/api/athletes/profile` and
`/api/athletes/{athlete_id}/profile`) may include optional
`personal_bests[*].percentile` values in `[0, 1]`. `average_times[*].percentile`
may also be present with the same semantics. Missing percentile data is
non-fatal: the `percentile` key is omitted for that segment rather than set to
null. Profile percentile cohorts are computed against historical results in the
same division and gender.

## Docs: Deploy to GitHub Pages

Publishing is automatic. The [`Docs`](https://github.com/vmatei2/pyrox-client/blob/main/.github/workflows/docs.yml)
workflow builds the site with `--strict` on every pull request that touches `docs/`,
`overrides/` or `mkdocs.yml`, and publishes to the `gh-pages` branch when those
changes land on `main`. Pages serves that branch, so nothing else has to happen.

To preview locally before opening the PR:

```bash
uv run mkdocs serve
```

Manual publishing stays available for the rare case where CI can't run — it
targets the same branch the workflow does:

```bash
uv run mkdocs build --strict
uv run mkdocs gh-deploy --clean
```

## Rate Limiting

`pyrox_api_service/ratelimit.py` applies a per-client-IP limit at the external
entry points. REST routes are limited by the parent app middleware; `/mcp` is
exempt there and limited at the mounted MCP sub-app boundary so the `/mcp` →
`/mcp/` redirect is not charged in addition to the served request. Both entry
points use the same limiter storage, so a caller's REST and MCP traffic still
share one per-IP window. It keys off the `Fly-Client-IP` header; requests without
it — the MCP tools' in-process calls into the REST app, and the test suite — are
exempt, so internal traffic is never throttled. Default is `60/minute`; override
with `PYROX_RATE_LIMIT` (a
[`limits`](https://limits.readthedocs.io) rate string, e.g. `120/minute`).

## Data Flow

The DuckDB artifact is built and published by the `hyrox_analysis` repository
(scrape → build → verify → publish to `s3://hyrox-results/processed/db/`). The
producer owns `latest.json`, which is a candidate pointer rather than the live
service contract.

At 20:00 UTC each Tuesday, `.github/workflows/refresh-data.yml` reads the
candidate and `deploy-current.json` directly from S3. It validates both with
the consumer's pointer parser and exits without touching Fly when their SHA-256
values match. For a supported new candidate, it writes the exact validated JSON
to `deploy-current.json`, then restarts or wakes the Fly machine and waits up to
12 minutes for `/api/health`. The workflow can also be dispatched manually for
an out-of-cycle backfill.

`pyrox_api_service/fetch_db.py` reads only the production pointer, verifies the
artifact's SHA-256, and swaps it into place on container boot. Code deploys are
handled separately by `.github/workflows/deploy.yml`. To roll data back,
repoint `deploy-current.json` at an earlier immutable artifact and refresh the
Fly machine; do not change the producer-owned `latest.json` from this repo.

## Backend: Local Run

From repository root:

```bash
uv pip install -e ".[api]"
export PYROX_DUCKDB_PATH=pyrox_duckdb
python -m pyrox_api_service.fetch_db  # download the published DuckDB artifact
uvicorn pyrox_api_service.app:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/api/health
```

## Frontend: Local Run

```bash
cd ui
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## iOS (Capacitor)

From `ui/`:

```bash
npm install
npm run build
npx cap add ios    # first time only
npm run build:cap
npx cap open ios
```

## Docker and Fly.io Notes

- Docker entrypoint uses `pyrox_api_service.mcp_app:app` (REST + MCP; see `Dockerfile`).
- Fly configuration is in `fly.toml`.
- Environment variables used by the service:
  - `PYROX_DUCKDB_PATH`
  - `PYROX_DB_POINTER_URL` — URL of the consumer-owned `deploy-current.json`
    pointer that `fetch_db` resolves on boot (defaults to the public CDN).
  - `PYROX_API_ALLOW_ORIGINS`
  - `PYROX_MCP_ALLOWED_HOSTS` (optional) — comma-separated Host allow-list. When
    set, enables MCP DNS-rebinding protection (Host/Origin validation). Left unset
    on the public Fly deploy on purpose: the endpoint is public, read-only, no-auth,
    and behind Fly's HTTPS proxy, so the protection adds no security but rejects
    browser/Electron MCP clients that send an `Origin` header (the Claude web /
    Desktop connector 403s with "Invalid Origin header" when this is set). The
    Claude Code CLI sends no `Origin`, so it works either way.
  - `PYROX_MCP_ALLOWED_ORIGINS` (optional) — comma-separated Origin allow-list.
    Only relevant when `PYROX_MCP_ALLOWED_HOSTS` is set; use it to allow specific
    browser origins (e.g. `https://claude.ai`) instead of disabling protection.
  - `PYROX_RATE_LIMIT` (optional) — per-client-IP edge rate (default `60/minute`).

If backend code, Dockerfile, or service module paths change, redeploy the Fly
app so the running image picks up updates.
