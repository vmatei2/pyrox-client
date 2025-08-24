from __future__ import annotations

import io
from pathlib import Path
import pandas as pd

from .manifest import load_manifest, _s3_open   # re-use your manifest loader + fsspec opener
from .config import get_config
from .errors import RaceNotFound, ParquetReadError


def list_races(season: int | None = None) -> pd.DataFrame:
    """
    Return available (season, location) pairs from the manifest.
    """
    df = load_manifest(refresh=True)
    if season is not None:
        try:
            df = df[df["season"] == int(season)]
        except ValueError as e:
            raise (ValueError(f"Input {season} is not of expected type. Please make sure you request an integer."))
    return (
        df[["season", "location"]]
        .drop_duplicates()
        .sort_values(["season", "location"])
        .reset_index(drop=True)
    )


def _local_parquet_cache_path(s3_key: str) -> Path:
    """
    Map an S3 key to a deterministic local cache path under ~/.cache/pyrox/parquet/.
    """
    cfg = get_config()
    p = cfg.cache_dir / "parquet" / s3_key.replace("/", "__")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _read_parquet_from_s3(s3_uri: str) -> pd.DataFrame:
    """
    Download the parquet bytes anonymously from S3 and read with fastparquet.
    """
    try:
        with _s3_open(s3_uri, "rb", anon=True) as f:
            data = f.read()
        return pd.read_parquet(io.BytesIO(data), engine="fastparquet")
    except Exception as e:
        raise ParquetReadError(f"Failed to read parquet from {s3_uri}: {e}")
# core.py
def _to_s3_uri(bucket: str, key: str) -> str:
    """Join bucket + key safely. If key is already a full s3:// URI, use it as-is."""
    key = key.strip()
    if key.startswith("s3://"):
        return key
    # allow bucket to be "s3://bucket" or just "bucket"
    if not bucket.startswith("s3://"):
        bucket = f"s3://{bucket}"
    return f"{bucket.rstrip('/')}/{key.lstrip('/')}"


def get_race(*, season: int, location: str) -> pd.DataFrame:
    """
    Resolve (season, location) -> s3_key via the manifest, then return the race DataFrame.

    Uses a simple local file cache. If the cached parquet fails to read,
    it is discarded and we re-fetch from S3.
    """
    manifest = load_manifest(refresh=True)

    # case-insensitive match on location
    row = manifest[
        (manifest["season"] == int(season)) &
        (manifest["location"].str.casefold() == location.casefold())
    ]

    if row.empty:
        raise RaceNotFound(f"No race found for season={season}, location='{location}'. "
                           f"Try: pyrox.list_races({season})")

    s3_key = row.iloc[0]["path"]
    cfg = get_config()
    s3_uri = _to_s3_uri(cfg.bucket, s3_key)

    # check local cache first
    local_path = _local_parquet_cache_path(s3_key)
    if local_path.exists():
        try:
            return pd.read_parquet(local_path, engine="fastparquet")
        except Exception:
            local_path.unlink(missing_ok=True)  # bad cache → remove and refetch

    # fetch from S3 and cache
    df = _read_parquet_from_s3(s3_uri)
    try:
        df.to_parquet(local_path, index=False, engine="fastparquet")
    except Exception:
        # cache failures should not fail the API
        pass
    return df

breakheere = 0
