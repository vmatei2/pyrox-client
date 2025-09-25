"""
PYROX Client - Hybrid S3 + API Data Access
"""

from __future__ import annotations
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import io

import pyrox.constants as _ct
from pyrox.errors import RaceNotFound

import httpx
import pandas as pd
import pyarrow.parquet as pq
import fsspec
import logging
logger = logging.getLogger("pyrox")
logger.addHandler(logging.NullHandler())  # prevent “No handler” warnings
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "pyrox"
DEFAULT_CDN_BASE = "https://d2wl4b7sx66tfb.cloudfront.net"  #  hit this for getting data via CCDN
#  DEFAULT_API_URL = "http://localhost:8000"  --> used for testing when running api in docker container


class CacheManager:
    """
    Handles local caching with ETags and TTL
    """
    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = cache_dir / "metadata.json"
        self._load_metadata()

    def _load_metadata(self):
        """Load cache metadata from file"""
        if self.metadata_file.exists():
            with open(self.metadata_file) as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}

    def _save_metadata(self):
        """Save cache metadata to file"""
        with open(self.metadata_file, "w") as f:
            json.dump(self.metadata, f, indent=2)

    def get_cache_path(self, key:str) -> Path:
        """get cahce file path for a given key"""
        #  using hash to avoid filesystem issues with long/special characters
        key_hash = hashlib.md5(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key_hash}.parquet"

    def is_fresh(self, key: str, ttl_seconds: int = _ct.TWO_HOURS_IN_SECONDS) -> bool:
        """Check if cached item is fresh enough"""
        if key not in self.metadata:
            return False

        cache_time = self.metadata[key].get('timestamp', 0)
        #  boolean checking if the difference between current time and latest cache time is lower than time to load decided above!
        return (time.time() - cache_time) < ttl_seconds

    def get_etag(self, key: str) -> Optional[str]:
        """Get etag for given key"""
        return self.metadata.get(key, {}).get('etag', None)

    def store(self, key:str, df: pd.DataFrame, etag:Optional[str]=None) -> None:
        """Store Dataframe in ache with metadata"""
        cache_path = self.get_cache_path(key)

        #  Store the data in cache
        df.to_parquet(cache_path, compression=_ct.SNAPPY_COMPRESSION, index=False)

        #  Store the metadata
        self.metadata[key] = {
            "timestamp": time.time(),
            "etag": etag,
            "path": str(cache_path),
            "rows": len(df),
            "size_mb": cache_path.stat().st_size / 1024 / 1024
        }

        self._save_metadata()

    def load(self, key: str) -> Optional[pd.DataFrame]:
        """Load DataFrame from cache if exists"""
        if key not in self.metadata:
            return None

        cache_path = self.get_cache_path(key)
        if not cache_path.exists():
            # Cleanup stale metadata
            del self.metadata[key]
            self._save_metadata()
            return None

        try:
            return pd.read_parquet(cache_path)
        except Exception as e:
            cache_path.unlink(missing_ok=True)
            if key in self.metadata:
                del self.metadata[key]
                self._save_metadata()
            return None

    def clear(self, pattern: str = "*"):
        """Clear cache items matching pattern"""
        import fnmatch
        to_remove = []
        for key in self.metadata:
            if fnmatch.fnmatch(key, pattern):
                cache_path = self.get_cache_path(key)
                cache_path.unlink(missing_ok=True)
                to_remove.append(key)

        for key in to_remove:
            del self.metadata[key]
        self._save_metadata()


class PyroxClient:
    def __init__(
            self,
            cache_dir: Optional[Path] = None,
            prefer_cdn: bool = True,
    ):
        self.cache = CacheManager(cache_dir or DEFAULT_CACHE_DIR)
        self.prefer_cdn = prefer_cdn


    def _http_client(self) -> httpx.Client:
        """Create HTTP client for API requests"""
        headers = {}
        return httpx.Client(
            base_url=self.api_url,
            headers=headers,
            timeout=30,
            follow_redirects=True
        )

    def _join_cdn(self, *parts: str) -> str:
        """https://d2wl4b7sx66tfb.cloudfront.net/processed/manifest/manifest.json"""
        return "/".join([DEFAULT_CDN_BASE.rstrip("/")] + [p.strip("/") for p in parts])

    def _get_manifest(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Load manifest csv via CDN with ETag-based caching.
        """
        cache_key = "manifest_cdn_v1"
        if not force_refresh and self.cache.is_fresh(cache_key, ttl_seconds=_ct.TWO_HOURS_IN_SECONDS):
            cached = self.cache.load(cache_key)
            if cached is not None:
                return cached

        url = self._join_cdn("manifest/latest.csv")
        etag_header = {}
        cached_etag = self.cache.get_etag(cache_key)
        if cached_etag and not force_refresh:
            etag_header["If-None-Match"] = cached_etag

        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(url, headers=etag_header)

            if resp.status_code == 304:
                cached = self.cache.load(cache_key)
                if cached is not None:
                    return cached
            resp.raise_for_status()
            # now need to convert the csv answer returned to pandas df
            df = pd.read_csv(io.BytesIO(resp.content))
            etag = resp.headers.get("etag")

            self.cache.store(cache_key, df, etag)
            return df

    def list_races(self, season: Optional[int] = None, force_refresh: bool = False) -> pd.DataFrame:
        """List available races"""
        df = self._get_manifest(force_refresh=force_refresh)

        if season is not None:
            df = df[df["season"] == int(season)]

        return (df[["season", "location"]]
                .drop_duplicates()
                .sort_values(["season", "location"])
                .reset_index(drop=True))

    def _manifest_row(self, season: int, location: str) -> pd.Series:
        df = self._get_manifest()
        mask = (df["season"] == int(season)) & (df["location"].str.casefold() == location.casefold())
        if not mask.any():
            raise RaceNotFound(f"No manifest entry for season={season}, location='{location}'")
        return df.loc[mask].iloc[0]

    def _s3_key_from_uri(self, s3_uri: str) -> str:
        if s3_uri.startswith("s3://"):
            ##  example output from splitting ['s3:', '', 'hyrox-results', 'processed', 'parquet/season=6/S6_2023_London__JGDMS4JI62E.parquet'] -- so taking 4th (due to cdn settings for bucket)
            return s3_uri.split("/", 4)[4]  # after bucket name
        return s3_uri

    def _cdn_url_from_manifest(self, season: int, location: str) -> str:
        row = self._manifest_row(season, location)
        # Prefer an explicit 'path' (s3 uri or key). If you already store 'cdn_path', you can use it directly.
        s3_path = str(row["path"])
        key = self._s3_key_from_uri(s3_path)
        return self._join_cdn(key)

    def _filters_for_race(self, gender: Optional[str], division: Optional[str]):
        filters = []
        if gender is not None:
            filters.append(("gender", "=", gender))
        if division is not None:
            filters.append(("division", "=", division))
        return filters or None

    def _get_race_from_cdn(self, season: int, location: str, gender: Optional[str] = None,
                           division: Optional[str] = None) -> pd.DataFrame:
        url = self._cdn_url_from_manifest(season, location)
        filters = self._filters_for_race(gender, division)
        try:
            with fsspec.open(url, "rb") as f:
                table = pq.read_table(f, filters=filters)
            if table.num_rows == 0:
                raise RaceNotFound(f"No rows after filters at {url} (gender={gender}, division={division})")
            return table.to_pandas(split_blocks=True, self_destruct=True)
        except RaceNotFound:
            raise
        except Exception as e:
            raise FileNotFoundError(f"CDN read failed for {url}: {e}") from e

    def get_race(
            self,
            season: int,
            location: str,
            gender: Optional[str] = None,
            division: Optional[str] = None,
            use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Function that either gets from cache or API or S3
        """
        # Create cache key
        cache_key = f"race_{season}_{location}_{gender or 'all'}_{division or 'all'}"

        # Try cache first
        if use_cache and self.cache.is_fresh(cache_key, ttl_seconds=7200):  # 2 hour TTL
            cached = self.cache.load(cache_key)
            logger.info(f"Using cached race {cache_key} and retrieing from cache")
            if cached is not None:
                logger.info(f"Found race - serving cache")
                return cached

        try:
            df = self._get_race_from_cdn(season, location, gender, division)
        except (RaceNotFound, FileNotFoundError) as e:
            raise FileNotFoundError(f"Read failed for season{season}, location={location} - {e}") from e

        #  before returning-convert station columns to their actual exercise name
        df = df.rename(columns=_ct.WORK_STATION_RENAMES)

        TIME_COLS = list(_ct.WORK_STATION_RENAMES.values()) + [
            "total_time", "work_time", "roxzone_time", "run_time"
        ]

        for c in TIME_COLS:
            if c in df.columns:
                df[c] = mmss_to_minutes(df[c])

        # Cache the result
        if use_cache:
            logger.info(f"Saving to cached race {cache_key}")
            self.cache.store(cache_key, df)
        return df

    def get_season(
            self,
            season: int,
            locations: Optional[Iterable[str]] = None,
            gender: Optional[str] = None,
            division: Optional[str] = None,
            max_workers: int = 8,
            use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get all races for a season
        """
        # Create cache key for the entire season query
        locations_key = ",".join(sorted(locations)) if locations else "all"
        cache_key = f"season_{season}_{locations_key}_{gender or 'all'}_{division or 'all'}"

        # Try cache first
        if use_cache and self.cache.is_fresh(cache_key, ttl_seconds=3600):  # 1 hour TTL
            cached = self.cache.load(cache_key)
            if cached is not None:
                return cached

        # Discover available races
        manifest = self.list_races(season=season)
        if locations:
            want = {loc.casefold() for loc in locations}
            manifest = manifest[manifest["location"].str.casefold().isin(want)]

        if manifest.empty:
            raise RaceNotFound(f"No races found for season={season}")

        def fetch_one(location: str) -> pd.DataFrame:
            return self.get_race(
                season=season,
                location=location,
                gender=gender,
                division=division,
                use_cache=use_cache
            )

        frames: List[pd.DataFrame] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(fetch_one, loc)
                for loc in manifest["location"].tolist()
            ]

            for future in as_completed(futures):
                try:
                    frame = future.result()
                    if not frame.empty:
                        frames.append(frame)
                except RaceNotFound:
                    continue  # Skip missing races

        if not frames:
            return pd.DataFrame()

        # Combine results
        result = pd.concat(frames, ignore_index=True)

        # Cache the combined result
        if use_cache:
            self.cache.store(cache_key, result)

        return result

    def _normalise_s3_path(self, path:str) -> str:
        """Small helper function to bascially remove s3 prefix and return URL that is epxected for pyarrow retrieval"""
        if path.startswith("s3://"):
            return path[5:]  #  strip 's3://'
        return path

    def clear_cache(self, pattern: str = "*"):
        """Clear local cache"""
        self.cache.clear(pattern)

    def cache_info(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_size = sum(
            item.get('size_mb', 0)
            for item in self.cache.metadata.values()
        )
        return {
            "cache_dir": str(self.cache.cache_dir),
            "total_items": len(self.cache.metadata),
            "total_size_mb": round(total_size, 2),
            "items": list(self.cache.metadata.keys())
        }

####    HELPERS     ######
#### To move to separate file (potentially class) as they grow
def mmss_to_minutes(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    # if it's MM:SS, promote to 0:MM:SS so pandas parses it
    s = s.where(s.str.count(":") == 2, "0:" + s)
    return pd.to_timedelta(s, errors="coerce").dt.total_seconds() / 60.0

