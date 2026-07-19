---
updated: 2026-07-19
sources:
  - src/pyrox/core.py
  - src/pyrox/reporting.py
  - src/pyrox/errors.py
  - pyrox_api_service/app.py
  - pyrox_api_service/reporting_queries.py
  - pyrox_api_service/race_report_loader.py
  - pyrox_api_service/database.py
  - pyrox_api_service/ratelimit.py
  - pyrox_api_service/mcp_app.py
  - pyrox_api_service/mcp_tools.py
  - ui/src
---

# Components: what bites if you don't know it

Synthesis only. For API surfaces read `docs/api.md` and `docs/mcp.md`; for the
data columns read `docs/data-model.md`.

## Client library (`src/pyrox`)

`get_race` resolves a manifest row (case-insensitive, with did-you-mean
suggestions on miss via `RaceNotFound`), reads parquet from the CDN with
gender/division pushed into `pq.read_table(filters=...)`, renames station
columns to readable names, and converts every time column to float minutes.
`get_season` fans that out across locations with a thread pool.

Gotchas:

- Cache keys encode all filters
  (`race_{season}_{location}_{year}_{gender}_{division}_{total_time_key}`). Add
  a filter parameter without extending the key and stale cache hits will alias.
- `total_time` filtering happens client-side after minute conversion; a scalar
  means strictly-less-than, a 2-tuple is an open interval.
- `mmss_to_minutes` coerces bad strings to NaN instead of raising, and column
  presence varies by season, so check before indexing.

## Reporting service (`pyrox_api_service`)

Layering is strict and worth keeping that way: `app.py` holds routes and HTTP
error mapping only, `reporting_queries.py` holds query and payload logic,
`database.py` resolves `PYROX_DUCKDB_PATH` and hands out read-only connections
through `ReportingClient`. Config errors return a generic 500; the real path
never reaches the client.

The race report path (`/api/reports/{result_id}`) used to hang in production
by materializing whole cohorts in pandas. Commit `a9cd559` moved it onto
`race_report_loader.py`, which computes stats and histograms inside DuckDB and
returns bounded row previews. New report features go through that loader. Full
cohort DataFrame loads on this path are a regression, not a style choice.

Rate limiting keys off the `Fly-Client-IP` header (default `60/minute`,
override with `PYROX_RATE_LIMIT`). Requests without the header are exempt on
purpose: that covers the MCP tools' in-process calls and the test suite. The
parent app exempts `/mcp` and the MCP sub-app applies the same shared limiter
at its own boundary, so the `/mcp` redirect isn't charged twice yet one per-IP
window covers both protocols.

Known cost still open: `ReportingQueries.reporting()` builds a new
`ReportingClient` and connection per call. See [active-work.md](active-work.md).

## MCP server

Ten read-only tools registered in `mcp_app.py`, logic in `mcp_tools.py`. The
usual flow an assistant takes: `find_athlete` to get a `result_id`, then
`get_race_report` or `get_deepdive`; or `list_filters` then `get_distribution`
or `get_rankings` for cohort questions.

Choices to preserve:

- Tools call the FastAPI app through a Starlette `TestClient`, so the real
  request path runs (validation, error mapping) with no socket, and tools
  unit-test as plain functions.
- Stable vocabularies (`Gender`, `Division`, metric names) are `Literal` types
  so valid values land in the tool schema. `age_group` and `location` stay free
  strings because they drift by season; a frozen list would reject new values.
- Default list limit is 20 to protect model context. Callers raise `limit`.
- DNS-rebinding protection is off deliberately. The endpoint is public,
  read-only, and behind Fly's HTTPS proxy; enabling it (by setting
  `PYROX_MCP_ALLOWED_HOSTS`) 403s browser-based MCP clients such as the Claude
  web connector. Read the comment blocks in `mcp_app.py` and `fly.toml` before
  touching this.

## UI (`ui/`)

Six page components map onto the service endpoints: Rankings, Report, Deepdive,
Planner, Compare, Profile. `api/client.js` is the single API client, base URL
from `VITE_API_BASE_URL`. The deployed web instance is
`pyrox-analytics.vercel.app`; a new frontend origin must be added to
`PYROX_API_ALLOW_ORIGINS` in `fly.toml` or CORS will reject it. QA context
lives in `ui/UX_ACCEPTANCE_CHECKLIST.md` and `ui/test_plan.md`.
