FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY api/ /app/api/
COPY src/ /app/src/
ENV PYTHONPATH=/app/src
RUN uv pip install --system --no-cache-dir fastapi uvicorn "polars>=1.5" s3fs boto3 pydantic-settings pandas platformdirs fastparquet pyarrow
EXPOSE 8080
CMD ["python","-m","uvicorn","api.app:app","--host","0.0.0.0","--port","8080"]
