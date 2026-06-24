FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY pyrox_api_service /app/pyrox_api_service
COPY pyrox_duckdb /app/pyrox_duckdb

RUN pip install --no-cache-dir uv \
    && uv pip install --system .[api]

EXPOSE 8080

ENV PYROX_DUCKDB_PATH=/app/pyrox_duckdb

# Serve the composed app: REST API (/api/*) plus the mounted MCP server (/mcp).
# --proxy-headers + --forwarded-allow-ips lets uvicorn trust Fly's X-Forwarded-Proto,
# so the /mcp -> /mcp/ mount redirect stays on https instead of downgrading to http
# (an http downgrade makes MCP clients like claude.ai abort and fall back to a
# failing OAuth sign-in flow).
CMD ["uvicorn", "pyrox_api_service.mcp_app:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
