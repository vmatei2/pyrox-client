from __future__ import annotations

import io
from typing import Optional, Tuple
from pathlib import Path

import fsspec
import pandas as pd

from pyrox.config import get_config
from pyrox.errors import ManifestUnavailable
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def _s3_open(path: str, mode: str = "rb", anon: bool = True):
    """
    Unified opener for S3 (via fsspec/s3fs).
    Parameters
    ----------
    path : str
        Full fsspec path, e.g. "s3://my-bucket/processed/manifest/latest.csv"
    mode : str
        File mode, usually "rb" for binary reads.
    anon : bool
        True => anonymous/public read (no AWS creds required).
    Returns
    -------
    contextmanager
        Use with 'with _s3_open(...) as f: data = f.read()'
    """
    # s3fs accepts the 'anon' kw to do public/unsigned requests
    return fsspec.open(path, mode=mode, **({"anon": True} if anon else {}))


def _cache_paths(name: str) -> Tuple[Path, Path]:
    """
    Compute cache locations for the manifest CSV and its ETag sidecar.
    We cache:
      - the CSV bytes as ~/.cache/pyrox/manifest.latest.csv
      - the ETag string as ~/.cache/pyrox/manifest.latest.csv.etag
    """
    cfg = get_config()
    cache_file = cfg.cache_dir / name
    meta_file = cfg.cache_dir / f"{name}.etag"
    return cache_file, meta_file


def _read_etag(meta_file: Path) -> Optional[str]:
    """Read the cached ETag string (if any)."""
    if meta_file.exists():
        try:
            etag = meta_file.read_text().strip()
            return etag or None
        except Exception:
            return None
    return None


def _head_s3(path: str) -> dict:
    """
    Fetch object metadata from S3 (cheap 'HEAD').

    Returns a dict similar to:
      {
        "ETag": "\"5d41402abc...\"",
        "LastModified": datetime,
        "Size": int,
        ...
      }

    Notes
    -----
    - We obtain the filesystem object from an open file handle (fo.fs),
      then call fs.info(path).
    - Not all gateways populate all keys—but ETag is common for S3.
    """
    # Open briefly to access underlying filesystem handle
    with fsspec.open(path, mode="rb", anon=True) as fo:
        fs = fo.fs  # type: ignore[attr-defined]
    return fs.info(path)


def load_manifest(refresh: bool = True) -> pd.DataFrame:
    """
    Load the manifest CSV as a pandas DataFrame with required columns:
      ['season', 'location', 'path']

    Caching strategy
    ----------------
    - Store the last-downloaded manifest under ~/.cache/pyrox.
    - On each call (when refresh=True), perform a HEAD request to get the
      current ETag. If it matches the cached ETag -> use cached CSV.
      Otherwise, re-download and update the cache.

    Parameters
    ----------
    refresh : bool
        If False, skip HEAD check and use cached file if present.
        If True (default), validate with ETag before deciding.

    Raises
    ------
    ManifestUnavailable
        If we cannot fetch or parse the manifest, and there is no usable cache.

    Returns
    -------
    pd.DataFrame
        Normalized manifest DataFrame.
    """
    cfg = get_config()
    s3_manifest_uri = f"{cfg.bucket}/{cfg.manifest_path}"
    cache_file, meta_file = _cache_paths("manifest.latest.csv")

    # 1) Try to fetch latest ETag (safe to fail; we'll fall back).
    current_etag: Optional[str] = None
    if refresh:
        try:
            info = _head_s3(s3_manifest_uri)
            # Some backends wrap ETag in quotes; we keep it as-is because
            # we compare exact strings on both sides.
            current_etag = info.get("ETag")
        except Exception as e:
            # HEAD can fail (e.g., transient network); we'll fall back to cache or GET.

            logger.info(f"Have not been able to retrieve head_s3 from the manifest uri: {s3_manifest_uri}. Encountered exception: {e}. Setting etag as none and looking for cache.")
            current_etag = None

    # 2) If we have a cached file and either:
    #    - HEAD failed (no current_etag), or
    #    - ETag matches the cached one,
    #   then load cached CSV immediately.
    cached_etag = _read_etag(meta_file)
    if cache_file.exists() and (current_etag is None or cached_etag == current_etag):
        try:
            return pd.read_csv(cache_file)
        except Exception:
            pass

    # 3) Re-download from S3 and update cache.
    try:
        with _s3_open(s3_manifest_uri, "rb", anon=True) as f:
            data = f.read()

        # Parse CSV from bytes buffer
        df = pd.read_csv(io.BytesIO(data))

        # Persist cache on success
        cache_file.write_bytes(data)
        if current_etag:
            meta_file.write_text(current_etag)

        # Basic schema checks
        required_base = ("season", "location")
        for col in required_base:
            if col not in df.columns:
                raise ManifestUnavailable(f"Manifest missing required column: {col}")

        if "path" not in df.columns:
            if "s3_key" in df.columns:
                df = df.rename(columns={"s3_key": "path"})
            else:
                raise ManifestUnavailable("Manifest missing required column: path")

        # Normalize dtypes; keeps downstream filters predictable
        df["season"] = df["season"].astype(int)
        df["location"] = df["location"].astype(str)
        df["path"] = df["path"].astype(str)

        return df

    except Exception as e:
        if cache_file.exists():
            try:
                return pd.read_csv(cache_file)
            except Exception:
                pass
        # No working cache → bail with a clear error
        raise ManifestUnavailable(f"Could not load manifest from {s3_manifest_uri}: {e}")

