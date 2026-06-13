# Reporting Service and UI

This repository includes a FastAPI reporting service and a Vite/React UI for
project workflows. This stack is separate from the published `pyrox-client`
package.

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
It exposes intent-shaped tools (`list_filters`, `find_athlete`, `get_distribution`,
`get_rankings`, `get_race_report`, `get_deepdive`, `get_athlete_profile`) whose
logic lives in `pyrox_api_service/mcp_tools.py` and calls the REST app in-process.
Add the URL `https://<host>/mcp` as a remote connector in Claude.

## Backend: Local Run

From repository root:

```bash
uv pip install -e ".[api]"
export PYROX_DUCKDB_PATH=pyrox_duckdb
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
  - `PYROX_API_ALLOW_ORIGINS`
  - `PYROX_MCP_ALLOWED_HOSTS` (optional) — comma-separated Host allow-list. When
    set, enables MCP DNS-rebinding protection (e.g. `pyrox-api.fly.dev`). Off by
    default since the data is public and the service sits behind Fly's proxy.
  - `PYROX_MCP_ALLOWED_ORIGINS` (optional) — comma-separated Origin allow-list.

If backend code, Dockerfile, or service module paths change, redeploy the Fly
app so the running image picks up updates.

