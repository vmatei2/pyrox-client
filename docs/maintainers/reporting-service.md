# Reporting Service and UI

This repository includes a FastAPI reporting service and a Vite/React UI for
project workflows. This stack is separate from the published `pyrox-client`
package.

## Canonical Backend Module

Use:

```bash
pyrox_api_service.app:app
```

There is a compatibility shim at `src/pyrox/api/` for legacy imports, but new
commands should use `pyrox_api_service.app:app`.

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

- Docker entrypoint uses `pyrox_api_service.app:app` (see `Dockerfile`).
- Fly configuration is in `fly.toml`.
- Environment variables used by the service:
  - `PYROX_DUCKDB_PATH`
  - `PYROX_API_ALLOW_ORIGINS`

If backend code, Dockerfile, or service module paths change, redeploy the Fly
app so the running image picks up updates.

