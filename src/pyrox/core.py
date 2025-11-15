"""
PYROX Client - retrieve Hyrox race results programatically
"""

from __future__ import annotations
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional
import io

from . import constants as _ct
from .errors import RaceNotFound

import httpx
import pandas as pd
import pyarrow.parquet as pq
import fsspec
import logging
logger = logging.getLogger("pyrox")
logger.addHandler(logging.NullHandler())  # prevent “No handler” warnings
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "pyrox"
DEFAULT_CDN_BASE = "https://d2wl4b7sx66tfb.cloudfront.net"  # getting data via CDN
#  DEFAULT_API_URL = "http://localhost:8000"  --> used for testing when running api in docker container


class CacheManager:
    """
    Handles local caching with ETags and TTL
    """
    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = cache_dir / "metadata.json"
        self._lock = RLock()
        self.metadata: Dict[str, Any] = {}
        self._load_metadata()

    def _load_metadata(self):
        """Load cache metadata from file"""
        with self._lock:
            if self.metadata_file.exists():
                with open(self.metadata_file) as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {}

    def _write_metadata_locked(self) -> None:
        with open(self.metadata_file, "w") as f:
            json.dump(self.metadata, f, indent=2)

    def get_cache_path(self, key:str) -> Path:
        """get cahce file path for a given key"""
        #  using hash to avoid filesystem issues with long/special characters
        key_hash = hashlib.md5(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key_hash}.parquet"

    def is_fresh(self, key: str, ttl_seconds: int = _ct.TWO_HOURS_IN_SECONDS) -> bool:
        """Check if cached item is fresh enough"""
        with self._lock:
            entry = self.metadata.get(key)

        if entry is None:
            return False

        cache_time = entry.get('timestamp', 0)
        #  boolean checking if the difference between current time and latest cache time is lower than time to load decided above!
        return (time.time() - cache_time) < ttl_seconds

    def get_etag(self, key: str) -> Optional[str]:
        """Get etag for given key"""
        with self._lock:
            entry = self.metadata.get(key)
            return entry.get('etag') if entry else None

    def store(self, key:str, df: pd.DataFrame, etag:Optional[str]=None) -> None:
        """Store Dataframe in ache with metadata"""
        cache_path = self.get_cache_path(key)

        #  Store the data in cache
        df.to_parquet(cache_path, compression=_ct.SNAPPY_COMPRESSION, index=False)

        #  Store the metadata
        with self._lock:
            self.metadata[key] = {
                "timestamp": time.time(),
                "etag": etag,
                "path": str(cache_path),
                "rows": len(df),
                "size_mb": cache_path.stat().st_size / 1024 / 1024
            }

            self._write_metadata_locked()

    def load(self, key: str) -> Optional[pd.DataFrame]:
        """Load DataFrame from cache if exists"""
        with self._lock:
            if key not in self.metadata:
                return None

        cache_path = self.get_cache_path(key)
        if not cache_path.exists():
            # Cleanup stale metadata
            with self._lock:
                if key in self.metadata:
                    del self.metadata[key]
                    self._write_metadata_locked()
            return None

        try:
            return pd.read_parquet(cache_path)
        except Exception as e:
            cache_path.unlink(missing_ok=True)
            with self._lock:
                if key in self.metadata:
                    del self.metadata[key]
                    self._write_metadata_locked()
            return None

    def clear(self, pattern: str = "*"):
        """Clear cache items matching pattern"""
        import fnmatch
        with self._lock:
            to_remove = [key for key in self.metadata if fnmatch.fnmatch(key, pattern)]

        for key in to_remove:
            cache_path = self.get_cache_path(key)
            cache_path.unlink(missing_ok=True)

        if to_remove:
            with self._lock:
                for key in to_remove:
                    self.metadata.pop(key, None)
                self._write_metadata_locked()

    def metadata_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self.metadata.copy()


class PyroxClient:
    def __init__(
            self,
            cache_dir: Optional[Path] = None
    ):
        self.cache = CacheManager(cache_dir or DEFAULT_CACHE_DIR)



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

    def _manifest_row(self, season: int, location: str, year:Optional[int] = None) -> pd.Series:
        df = self._get_manifest()

        mask = (df["season"].eq(int(season))
                & df["location"].str.casefold().eq(location.casefold()))
        if year is not None:
            mask &= df["year"].eq(int(year))
        if not mask.any():
            raise RaceNotFound(f"No manifest entry for season={season}, location='{location}'")
        return df.loc[mask].iloc[0]

    def _s3_key_from_uri(self, s3_uri: str) -> str:
        if s3_uri.startswith("s3://"):
            ##  example output from splitting ['s3:', '', 'hyrox-results', 'processed', 'parquet/season=6/S6_2023_London__JGDMS4JI62E.parquet'] -- so taking 4th (due to cdn settings for bucket)
            return s3_uri.split("/", 4)[4]  # after bucket name
        return s3_uri

    def _cdn_url_from_manifest(self, season: int, location: str, year: Optional[int] = None) -> str:
        row = self._manifest_row(season, location, year)
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

    def _get_race_from_cdn(self, season: int, location: str, year: Optional[int]=None, gender: Optional[str] = None,
                           division: Optional[str] = None) -> pd.DataFrame:
        url = self._cdn_url_from_manifest(season, location, year)
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
            year: Optional[int] = None,
            gender: Optional[str] = None,
            division: Optional[str] = None,
            total_time: Optional[float | tuple[Optional[float], Optional[float]]] = None,
            use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch race results, optionally filtering by gender, division, and total time.

        Args:
            season: Hyrox season identifier.
            location: Host city/location for the race.
            year: Optional calendar year to disambiguate multi-year locations.
            gender: Optional gender filter applied server-side when available.
            division: Optional division filter applied server-side when available.
            total_time: When provided, filters athletes based on their total race time
                expressed in minutes. Supply a single value to return results with a
                total time strictly less than the value, or a two-element tuple to
                represent an open interval ``(lower, upper)`` where either bound may be
                ``None`` to leave that side unbounded.
            use_cache: Whether to read/write from the local cache.
        """

        def _format_bound(value: Optional[float]) -> str:
            if value is None:
                return "none"
            return f"{float(value):g}"

        if total_time is None:
            lower_bound: Optional[float] = None
            upper_bound: Optional[float] = None
            total_time_key = "all"
        elif isinstance(total_time, tuple):
            if len(total_time) != 2:
                raise ValueError("total_time tuple must contain exactly two values (lower, upper)")
            raw_lower, raw_upper = total_time
            lower_bound = float(raw_lower) if raw_lower is not None else None
            upper_bound = float(raw_upper) if raw_upper is not None else None
            total_time_key = f"range_{_format_bound(lower_bound)}_{_format_bound(upper_bound)}"
        else:
            lower_bound = None
            upper_bound = float(total_time)
            total_time_key = f"lt_{_format_bound(upper_bound)}"

        # Create cache key
        cache_key = (
            f"race_{season}_{location}_{year or 'all'}_{gender or 'all'}_"
            f"{division or 'all'}_{total_time_key}"
        )

        # Try cache first
        if use_cache and self.cache.is_fresh(cache_key, ttl_seconds=7200):  # 2 hour TTL
            cached = self.cache.load(cache_key)
            logger.info(f"Using cached race {cache_key} and retrieing from cache")
            if cached is not None:
                logger.info(f"Found race - serving cache")
                return cached

        try:
            df = self._get_race_from_cdn(season, location, year, gender, division)
        except (RaceNotFound, FileNotFoundError) as e:
            raise FileNotFoundError(f"Read failed for season{season}, location={location} - {e}") from e

        # Before returning, convert station columns to their exercise names
        df = df.rename(columns=_ct.WORK_STATION_RENAMES)

        time_cols = list(_ct.WORK_STATION_RENAMES.values()) + [
            "total_time", "work_time", "roxzone_time", "run_time"
        ]

        for col in time_cols:
            if col in df.columns:
                df[col] = mmss_to_minutes(df[col])

        if lower_bound is not None or upper_bound is not None:
            if "total_time" not in df.columns:
                raise KeyError("total_time column is not available in the retrieved race data")
            total_time_series = df["total_time"].astype(float)
            mask = pd.Series(True, index=df.index)
            if lower_bound is not None:
                mask &= total_time_series > lower_bound
            if upper_bound is not None:
                mask &= total_time_series < upper_bound
            df = df[mask].reset_index(drop=True)

        # Cache the result
        if use_cache:
            logger.info(f"Saving to cached race {cache_key}")
            self.cache.store(cache_key, df)
        return df

    def get_athlete_in_race(self,
                            season: int,
                            location: str,
                            athlete_name: str,
                            year: Optional[int] = None,
                            gender: Optional[str] = None,
                            division: Optional[str] = None,
                            max_workers: int = 8,
                            use_cache: bool = True):
        """
        Get a specific athlete's (or doubles pair) race entry
        :param season:
        :param location:
        :param athlete_name:
        :param year:
        :param gender:
        :param division:
        :param max_workers:
        :param use_cache:
        :return:
        """

        if athlete_name is None:
            raise ValueError(f"Pleaes provide athlete name value.")

        df = self.get_race(
            season=season,
            location=location,
            year=year,
            gender=gender,
            division=division,
            use_cache=use_cache
        )

        if "name" not in df.columns:
            raise KeyError("Column 'name not found in race data.")

        lower_name = athlete_name.strip().casefold()

        df = df[df['name'].astype(str).str.casefold().str.contains(lower_name)]

        return df.reset_index(drop=True)


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
        metadata = self.cache.metadata_snapshot()
        total_size = sum(
            item.get('size_mb', 0)
            for item in metadata.values()
        )
        return {
            "cache_dir": str(self.cache.cache_dir),
            "total_items": len(metadata),
            "total_size_mb": round(total_size, 2),
            "items": list(metadata.keys())
        }

####    HELPERS     ######
#### To move to separate file (potentially class) as they grow
def mmss_to_minutes(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    # if it's MM:SS, promote to 0:MM:SS so pandas parses it
    s = s.where(s.str.count(":") == 2, "0:" + s)
    return pd.to_timedelta(s, errors="coerce").dt.total_seconds() / 60.0


if __name__ == '__main__':
    client = PyroxClient()

    s6 = client.get_season(6, use_cache=False)
    s7 = client.get_season(7, use_cache=False)
    s8 = client.get_season(8, use_cache=False)

    breakhere = 0
