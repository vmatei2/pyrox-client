"""
PYROX Client - Hybrid S3 + API Data Access
"""

from __future__ import annotations
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from os.path import split
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import pyrox.constants as _ct
from pyrox.errors import ApiError, RaceNotFound

import httpx
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.dataset as ds
from pyarrow import fs


# Configuration
DEFAULT_API_URL = "https://pyrox-api-proud-surf-3131.fly.dev"
DEFAULT_API_KEY = os.getenv("PYROX_API_KEY")
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "pyrox"
DEFAULT_S3_BUCKET = "hyrox-results"
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
            api_url: str = DEFAULT_API_URL,
            api_key: Optional[str] = DEFAULT_API_KEY,
            cache_dir: Optional[Path] = None,
            s3_bucket: str = DEFAULT_S3_BUCKET,
            prefer_s3: bool = True  #  Default to S3 for the bulk of the data
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.cache = CacheManager(cache_dir or DEFAULT_CACHE_DIR)
        self.s3_bucket = s3_bucket
        self.prefer_s3 = prefer_s3

        #  Setup S3 filesystem
        self.s3_fs = fs.S3FileSystem(region="eu-west-2", anonymous=True)

    def _http_client(self) -> httpx.Client:
        """Create HTTP client for API requests"""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return httpx.Client(
            base_url=self.api_url,
            headers=headers,
            timeout=30,
            follow_redirects=True
        )

    def _get_manifest(self, force_refresh: bool = False) -> pd.DataFrame:
        """Get race manifest (cached, with ETag support)"""
        cache_key = "manifest"

        if not force_refresh and self.cache.is_fresh(cache_key, ttl_seconds=_ct.TWO_HOURS_IN_SECONDS): #
            cached = self.cache.load(cache_key)
            if cached is not None:
                return cached

        with self._http_client() as client:
            headers = {}
            cached_etag = self.cache.get_etag(cache_key)
            if cached_etag and not force_refresh:
                headers["If-None-Match"] = cached_etag

            response = client.get("/v1/manifest", headers=headers)

            if response.status_code == 304:  # Not modified
                cached = self.cache.load(cache_key)
                if cached is not None:
                    return cached

            if response.status_code != 200:
                raise ApiError(f"Manifest fetch failed: {response.status_code} {response.text}")

            rows = response.json()
            df = pd.DataFrame(rows)

            etag = response.headers.get('etag')
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

    def _get_race_from_s3(
            self,
            season: int,
            location: str,
            gender: Optional[str] = None,
            division: Optional[str] = None
    ) -> pd.DataFrame:
        """Get race data directly from S3 (faster for bulk queries)"""

        ### To-do -- this can/should use the maniefest to get the exact s3 path for my race!
        #  To get the path - let's first get it from the manifest (this will be cached on a subsequent retry)
        manifest_df = self._get_manifest()
        s3_path = manifest_df.loc[(manifest_df["location"] == location) & (manifest_df["season"] == season), "path"].iloc[0]
        s3_path = self._normalise_s3_path(s3_path)
        try:
            # List files in the partition
            filter = None
            if gender is not None:
                expr = (ds.field("gender") == gender)
                filter = expr if filter is None else (filter & expr)
            if division is not None:
                expr = (ds.field("division") == division)
                filter = expr if filter is None else (filter & expr)

            #  Create the dataset -- PyArrow discovers the partitions

            dataset = ds.dataset(s3_path, filesystem=self.s3_fs, format="parquet")
            table = dataset.to_table(filter=filter, use_threads=True)
            if table.num_rows == 0:
                raise RaceNotFound(f"No race data found at path: {s3_path}, for season {season}, location: {location}")
            #  split blocks - splits groups of columns of same dtype into contiguous numpy blocks --> mpre efficient memory layout in Pandas
            #  self_destruct = True - lets Arrow free the original buffers immediately after conversion, saving memory
            return table.to_pandas(split_blocks=True, self_destruct=True)

        except Exception as e:
            # Fall back to API if S3 access fails
            if "No race data found" in str(e) or isinstance(e, RaceNotFound):
                raise

    def _get_race_from_api(
            self,
            season: int,
            location: str,
            gender: Optional[str] = None,
            division: Optional[str] = None
    ) -> pd.DataFrame:
        params = {}
        if gender:
            params["gender"] = gender
        if division:
            params["division"] = division

        with self._http_client() as client:
            response = client.get(f"/v1/race/{int(season)}/{location}", params=params)

            if response.status_code == 404:
                raise RaceNotFound(f"No race found for season={season}, location='{location}'")
            if response.status_code != 200:
                raise ApiError(f"Race fetch failed: {response.status_code} {response.text}")

            rows = response.json()
            return pd.DataFrame(rows)

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
            if cached is not None:
                return cached

        # Choose data source
        if self.prefer_s3:
            try:
                df = self._get_race_from_s3(season, location, gender, division)
            except (RaceNotFound, FileNotFoundError):
                df = self._get_race_from_api(season, location, gender, division)
        else:
            df = self._get_race_from_api(season, location, gender, division)

        # Cache the result
        if use_cache:
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


if __name__ == '__main__':
    client = PyroxClient(prefer_s3=True)
    client._get_manifest()
