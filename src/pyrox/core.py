from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, Optional


import io
from pathlib import Path
from pyrox.manifest import load_manifest, _s3_open
import pandas as pd
from pyrox.config import get_config
from pyrox.errors import RaceNotFound, ParquetReadError



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


def get_season(
    season: int,
    locations: Optional[Iterable[str]] = None,
    columns: Optional[list[str]] = None,
    max_workers: int = 8,
) -> pd.DataFrame:
    """
    Load and concatenate all race DataFrames for a given season.

    Parameters
    ----------
    season : int
        Season number (e.g., 7).
    locations : Optional[Iterable[str]]
        Optional subset of locations to include (case-insensitive).
    columns : Optional[list[str]]
        Optional column projection (subset of columns to return).
        Note: with the current byte-read helper, this is a post-read projection.
    max_workers : int
        Thread pool size for parallel file loads.

    Returns
    -------
    pd.DataFrame
        Concatenated DataFrame with all rows for the season.
        Adds `season` and `location` columns to each row.
    """
    manifest = load_manifest(refresh=True)
    m = manifest[manifest["season"] == int(season)].copy()

    if locations:
        want = {loc.casefold() for loc in locations}
        m = m[m["location"].str.casefold().isin(want)]

    if m.empty:
        raise RaceNotFound(f"No races found for season={season}. Try list_races({season}).")

    cfg = get_config()

    def _load_one(row: pd.Series) -> pd.DataFrame:
        s3_key = row["path"]           # manifest column name
        s3_uri = _to_s3_uri(cfg.bucket, s3_key)
        local_path = _local_parquet_cache_path(s3_key)

        # 1) try cache
        df = None
        if local_path.exists():
            try:
                df = pd.read_parquet(local_path, engine="fastparquet")
            except Exception:
                local_path.unlink(missing_ok=True)

        # 2) fetch if needed
        if df is None:
            df = _read_parquet_from_s3(s3_uri)
            try:
                df.to_parquet(local_path, index=False, engine="fastparquet")
            except Exception:
                pass  # cache failures shouldn't break the call

        # Optional projection (post-read)
        if columns:
            missing = [c for c in columns if c not in df.columns]
            if missing:
                raise ParquetReadError(f"Missing columns {missing} in {s3_key}")
            df = df[columns]

        # annotate for provenance
        df = df.copy()
        df["season"] = row["season"]
        df["location"] = row["location"]
        return df

    frames: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_load_one, r) for _, r in m.iterrows()]
        for fut in as_completed(futures):
            frames.append(fut.result())

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    # nice-to-have sort if columns exist
    sort_cols = [c for c in ["location", "bib", "total_time_s"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols).reset_index(drop=True)
    return out


df = get_season(season=6)

