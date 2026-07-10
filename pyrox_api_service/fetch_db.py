"""Boot-time fetch of the DuckDB artifact published by the scraping pipeline.

The hyrox_analysis repo builds the database and publishes it to S3 as an
immutable object plus a ``latest.json`` pointer (key, sha256, schema_version,
provenance). This module downloads the pointer, verifies the artifact
checksum, and atomically swaps the file into place before the API starts.
The service itself never builds or ingests data.

Run as a container entrypoint step:

    python -m pyrox_api_service.fetch_db && uvicorn pyrox_api_service.mcp_app:app ...

Environment:
    PYROX_DB_POINTER_URL  URL of latest.json (default: the public CDN pointer)
    PYROX_DUCKDB_PATH     where to place the artifact (default: pyrox_duckdb)
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)

# Highest artifact schema this service understands; the pipeline bumps the
# pointer's schema_version on breaking changes and we refuse to serve those.
SUPPORTED_SCHEMA_VERSION = 1

DEFAULT_POINTER_URL = "https://d2wl4b7sx66tfb.cloudfront.net/db/latest.json"
POINTER_URL_ENV = "PYROX_DB_POINTER_URL"
DUCKDB_PATH_ENV = "PYROX_DUCKDB_PATH"

_DOWNLOAD_TIMEOUT = httpx.Timeout(30.0, read=600.0)


class ArtifactFetchError(RuntimeError):
    """Raised when the pointer or artifact fails validation."""


@dataclass(frozen=True)
class ArtifactPointer:
    key: str
    sha256: str
    size_bytes: int
    schema_version: int
    built_at: str


def parse_pointer(payload: dict[str, Any]) -> ArtifactPointer:
    """Validate the latest.json payload and return the pointer contract."""
    for field in ("key", "sha256", "size_bytes", "schema_version"):
        if field not in payload:
            raise ArtifactFetchError(f"pointer is missing required field: {field}")

    schema_version = int(payload["schema_version"])
    if schema_version > SUPPORTED_SCHEMA_VERSION:
        raise ArtifactFetchError(
            f"pointer schema_version {schema_version} is newer than supported "
            f"{SUPPORTED_SCHEMA_VERSION}; upgrade the service before serving it"
        )

    return ArtifactPointer(
        key=str(payload["key"]),
        sha256=str(payload["sha256"]),
        size_bytes=int(payload["size_bytes"]),
        schema_version=schema_version,
        built_at=str(payload.get("built_at", "")),
    )


def artifact_url(pointer_url: str, key: str) -> str:
    """Resolve the artifact URL against the pointer's origin.

    Artifact keys are bucket-root-relative, and the CDN maps to the bucket
    root, so the artifact lives at ``<pointer origin>/<key>``.
    """
    scheme, netloc, _, _, _ = urlsplit(pointer_url)
    return urlunsplit((scheme, netloc, f"/{key.lstrip('/')}", "", ""))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_artifact(
    pointer_url: str,
    target_path: Path,
    client: Optional[httpx.Client] = None,
) -> ArtifactPointer:
    """Download the current artifact unless the local copy already matches."""
    own_client = client is None
    http = client or httpx.Client(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True)
    try:
        # Cache-busting param so a CDN-cached pointer does not pin us to a
        # stale artifact across restarts.
        response = http.get(pointer_url, params={"ts": int(time.time())})
        response.raise_for_status()
        pointer = parse_pointer(response.json())

        target = Path(target_path)
        if target.exists() and sha256_file(target) == pointer.sha256:
            logger.info("Local artifact already matches %s; skipping download", pointer.key)
            return pointer

        url = artifact_url(pointer_url, pointer.key)
        logger.info("Downloading %s (%s bytes)", url, pointer.size_bytes)
        tmp_target = target.with_name(target.name + ".download")
        with http.stream("GET", url) as stream:
            stream.raise_for_status()
            with tmp_target.open("wb") as handle:
                for chunk in stream.iter_bytes():
                    handle.write(chunk)

        try:
            actual_sha = sha256_file(tmp_target)
            if actual_sha != pointer.sha256:
                raise ArtifactFetchError(
                    f"sha256 mismatch for {pointer.key}: "
                    f"expected {pointer.sha256}, got {actual_sha}"
                )
            os.replace(tmp_target, target)
        finally:
            tmp_target.unlink(missing_ok=True)

        logger.info("Artifact %s in place at %s", pointer.key, target)
        return pointer
    finally:
        if own_client:
            http.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    pointer_url = os.getenv(POINTER_URL_ENV, "").strip() or DEFAULT_POINTER_URL
    target = Path(os.getenv(DUCKDB_PATH_ENV, "").strip() or "pyrox_duckdb")
    pointer = fetch_artifact(pointer_url, target)
    logger.info(
        "Serving artifact key=%s built_at=%s schema_version=%s",
        pointer.key,
        pointer.built_at,
        pointer.schema_version,
    )


if __name__ == "__main__":
    main()
