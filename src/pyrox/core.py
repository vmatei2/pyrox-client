from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, Optional
import os
import pandas as pd
import httpx

DEFAULT_API_URL = "https://pyrox-api-proud-surf-3131.fly.dev"
DEFAULT_API_KEY = os.getenv("PYROX_API_KEY")  #  optional for now as not used on api side
#  DEFAULT_API_URL = "http://localhost:8000"  --> used for testing when running api in docker container
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

def get_race(*, season: int, location: str, gender: Optional[str] = None, division: Optional[str] = None,
             base_url: str | None = None, api_key: str | None = DEFAULT_API_KEY) -> pd.DataFrame:
    params = {}
    if gender: params["gender"] = gender
    if division: params["division"] = division
    with _client(base_url, api_key) as c:
        r = c.get(f"/v1/race/{int(season)}/{location}", params=params)
        if r.status_code == 404:
            raise RaceNotFound(f"No race found for season={season}, location='{location}'")
        if r.status_code != 200:
            raise ApiError(f"race fetch failed: {r.status_code} {r.text}")
        rows = r.json()  # list[dict]
    df = pd.DataFrame(rows)
    return df


def get_season(season: int, locations: Optional[Iterable[str]] = None,
               max_workers: int = 8, base_url: str | None = None, api_key: str | None = DEFAULT_API_KEY,
               gender: Optional[str] = None, division: Optional[str] = None) -> pd.DataFrame:
    # discover available races first (avoids 404 spam)
    m = list_races(season=season, base_url=base_url, api_key=api_key)
    if locations:
        want = {loc.casefold() for loc in locations}
        m = m[m["location"].str.casefold().isin(want)]
    if m.empty:
        raise RaceNotFound(f"No races found for season={season}")
    #  function to get one data frame for a specifc race
    def _one(loc: str) -> pd.DataFrame:
        return get_race(season=season, location=loc, gender=gender, division=division, base_url=base_url, api_key=api_key)

    frames: list[pd.DataFrame] = []
    #  split the work to get the dataframe across multiple workers
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_one, loc) for loc in m["location"].tolist()]
        for f in as_completed(futs):
            frames.append(f.result())
    #  join and return the data!
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)

    return out


