# core_api.py  (replacement for your previous core.py that hit S3)

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, Optional
import os
import pandas as pd
import httpx

DEFAULT_API_URL = os.getenv("PYROX_API_URL", "https://pyrox-api-proud-surf-3131.fly.dev")
DEFAULT_API_KEY = os.getenv("PYROX_API_KEY")  # optional

class ApiError(RuntimeError): ...
class RaceNotFound(RuntimeError): ...

def _client(base_url: str | None = None, api_key: str | None = None) -> httpx.Client:
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return httpx.Client(base_url=base_url or DEFAULT_API_URL, headers=headers, timeout=30)

def list_races(season: int | None = None, base_url: str | None = None, api_key: str | None = DEFAULT_API_KEY) -> pd.DataFrame:
    with _client(base_url, api_key) as c:
        r = c.get("/v1/manifest")
        if r.status_code != 200:
            raise ApiError(f"manifest failed: {r.status_code} {r.text}")
        rows = r.json()  # [{season, location, path}, ...]
    df = pd.DataFrame(rows)
    if season is not None:
        df = df[df["season"] == int(season)]
    return df[["season", "location"]].drop_duplicates().sort_values(["season", "location"]).reset_index(drop=True)

def get_race(*, season: int, location: str, sex: Optional[str] = None, division: Optional[str] = None,
             base_url: str | None = None, api_key: str | None = DEFAULT_API_KEY) -> pd.DataFrame:
    params = {}
    if sex: params["sex"] = sex
    if division: params["division"] = division
    with _client(base_url, api_key) as c:
        r = c.get(f"/v1/race/{int(season)}/{location}", params=params)
        if r.status_code == 404:
            raise RaceNotFound(f"No race found for season={season}, location='{location}'")
        if r.status_code != 200:
            raise ApiError(f"race fetch failed: {r.status_code} {r.text}")
        rows = r.json()  # list[dict]
    df = pd.DataFrame(rows)
    # add provenance if missing
    if "season" not in df.columns:
        df["season"] = int(season)
    if "location" not in df.columns:
        df["location"] = location
    return df

def get_season(season: int, locations: Optional[Iterable[str]] = None, columns: Optional[list[str]] = None,
               max_workers: int = 8, base_url: str | None = None, api_key: str | None = DEFAULT_API_KEY,
               sex: Optional[str] = None, division: Optional[str] = None) -> pd.DataFrame:
    # discover available races first (avoids 404 spam)
    m = list_races(season=season, base_url=base_url, api_key=api_key)
    if locations:
        want = {loc.casefold() for loc in locations}
        m = m[m["location"].str.casefold().isin(want)]
    if m.empty:
        raise RaceNotFound(f"No races found for season={season}")

    def _one(loc: str) -> pd.DataFrame:
        return get_race(season=season, location=loc, sex=sex, division=division, base_url=base_url, api_key=api_key)

    frames: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_one, loc) for loc in m["location"].tolist()]
        for f in as_completed(futs):
            frames.append(f.result())

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)

    if columns:
        missing = [c for c in columns if c not in out.columns]
        if missing:
            raise ApiError(f"Missing columns in response: {missing}")
        out = out[columns + [c for c in ["season", "location"] if c in out.columns]]
    sort_cols = [c for c in ["location", "bib", "total_time_s"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols).reset_index(drop=True)
    return out

# quick smoke test:
if __name__ == "__main__":
    print(list_races(7).head())
    df = get_race(season=7, location="barcelona")
    breakhere = 0
