from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional, Dict, Any

import polars as pl
import pyarrow.dataset as pyarrow_ds
import s3fs
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from pyrox.config import get_config
from pyrox.manifest import load_manifest
from pyrox.config import _DEFAULT_MANIFEST
from pyrox.config import _DEFAULT_BUCKET
from pyrox.constants import WORK_STATION_RENAMES, ONE_HOUR_IN_SECONDS, ONE_HOUR_IN_MINUTES


class Settings(BaseSettings):
    pyrox_bucket: str = os.getenv("PYROX_BUCKET", "s3://hyrox-results")
    api_key: Optional[str] = os.getenv("PYROX_API_KEY")
    aws_region: str = os.getenv("AWS_REGION", "eu-west-2")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.pyrox_bucket:
        raise RuntimeError("PYROX_BUCKET env var not set.")
    return s


# ----- Auth Layer (simple API Key) ----
def check_api_key(settings: Settings = Depends(get_settings),
                  authorization: Optional[str] = Header(default=None)) -> None:
    if not settings.api_key:
        return  ## dev mode: no auth --> setting.api_key simply comes from the environment - null for now
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API Key")

    token = authorization.split(" ", 1)[1]
    if token != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API Key")


###   Manifest Loader
@lru_cache(maxsize=1)
def _load_manifest_df():
    return load_manifest(refresh=True)


def _s3_uri_for(season: int, location: str, bucket: str) -> str:
    """
    Return the s3 path from the manifest for a specific season / location - given the S3 Bucket we are looking in
    :param season:
    :param location:
    :param bucket:
    :return:
    """
    m = _load_manifest_df()
    row = m[(m["season"] == season) & (m['location'].str.casefold() == location.casefold())]

    if row.empty:
        raise HTTPException(status_code=404, detail="No race for season={season}, location={location}")
    key = row.iloc[0]["path"]
    if key.startswith("s3://"):
        return key
    return f"s3://{bucket.rstrip('/')}/{key.lstrip('/')}"

class ManifestRow(BaseModel):
    season: int
    location: str
    path: str


app = FastAPI(title="pyrox API", version="1.0.0")


@app.get("/v1/healthz")
def healthz() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/v1/manifest", response_model=List[ManifestRow])
def manifest(_: None = Depends(check_api_key)):
    """
    Return the raw manifest rows (season, location, path
    :param _:
    :return:
    """
    df = _load_manifest_df()
    return df[["season", "location", "path"]].to_dict(orient="records")

@app.get("/v1/season/{season}/races")
def list_season_races(season:int, settings:Settings = Depends(get_settings)):
    """
    api endpoint to list all available races in a given season
    :param season:
    :param settings:
    :return:
    """
    manifest_uri = f"{_DEFAULT_BUCKET}/{_DEFAULT_MANIFEST}"
    fs = s3fs.S3FileSystem(anon=True)
    try:
        ds = pyarrow_ds.dataset(manifest_uri, filesystem=fs, format="csv")
        lf = pl.scan_pyarrow_dataset(ds)
    except Exception as e:
        raise HTTPException(502, detail=f"Manifest read failed: {type(e).__name__} : {e}")

    df = lf.filter(pl.col("season") == season)\
        .select(["season", "location"])\
        .unique(subset=["season", "location"])\
        .collect()

    if df.height == 0:
        raise HTTPException(404, detail=f"No races found for season: {season}")
    return df.to_dicts()


@app.get("/v1/race/{season}/{location}")
def get_race(season: int, location: str, sex: Optional[str] = Query(default=None, description="Filter by sex"),
             division: Optional[str] = Query(default=None, description="Open / Pro"),
             settings: Settings = Depends(get_settings)):
    """
    :return:
    """
    s3_uri = _s3_uri_for(season, location, settings.pyrox_bucket)
    fs = s3fs.S3FileSystem(anon=True)
    try:
        ds = pyarrow_ds.dataset(s3_uri, filesystem=fs, format="parquet")
        lf = pl.scan_pyarrow_dataset(ds)
    except Exception as e:
        raise HTTPException(502, detail=f"S3 read failed: {type(e).__name__} : {e}")

    if sex:
        lf = lf.filter(pl.col("sex") == sex)
    if division:
        print("hit division")
        print(division)
        lf = lf.filter(pl.col("division") == division)
    df = lf.collect()
    #  before returning to client - convert station columns to their actual exercise name
    df = df.rename(WORK_STATION_RENAMES)
    return df.to_dicts()


@app.get("/v1/race/{season}/{location}/stats")
def get_race_stats(season: int,
                   location: str,
                   gender: Optional[str] = Query(default=None),
                   division: Optional[str] = Query(default=None, description="Open / Pro"),
                   settings: Settings = Depends(get_settings),
                   _: None = Depends(check_api_key)):
    """Simple race stats - both overall and by gender / division """
    s3_uri = _s3_uri_for(season, location, settings.pyrox_bucket)
    fs = s3fs.S3FileSystem(anon=True)

    try:
        ds = pyarrow_ds.dataset(s3_uri, filesystem=fs, format="parquet")
        lf = pl.scan_pyarrow_dataset(ds)
    except Exception as e:
        raise HTTPException(502, detail=f"S3 read failed: {type(e).__name__} : {e}")

    if gender: lf = lf.filter(pl.col("gender") == gender)
    if division: lf = lf.filter(pl.col("division") == division)

    str_time_col = "total_time"
    converted_time_col = "time_in_seconds"
    parts = pl.col(str_time_col).str.split(":")
    n = parts.list.len()
    sec = parts.list.get(-1).cast(pl.Float64)
    minu = pl.when(n >= 2).then(parts.list.get(-2).cast(pl.Int64)).otherwise(0)
    hour = pl.when(n >= 3).then(parts.list.get(-3).cast(pl.Int64)).otherwise(0)
    lf = lf.with_columns((hour * ONE_HOUR_IN_SECONDS + minu * 60 + sec).alias(converted_time_col))
    hours = (pl.col(converted_time_col).cast(pl.Float64) / ONE_HOUR_IN_MINUTES)

    overall = (
        lf.select([
            hours.min().alias("fastest"),
            hours.mean().alias("average"),
            pl.len().alias("number_of_athletes"),
        ])
        .collect()
        .to_dicts()[0]
    )

    groups = (
        lf.group_by(["gender", "division"])
        .agg([
            pl.len().alias("number_of_athletes"),
            hours.min().alias("fastest"),
            hours.mean().alias("average"),
        ])
        .sort(["gender", "division"])
        .collect()
        .to_dicts()
    )

    res = {"race": {"season": season, "location": location}, "summary":overall, "groups": groups}
    return res
