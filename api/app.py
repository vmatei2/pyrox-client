from __future__ import annotations

import os

from pyrox.config import get_config
from functools import lru_cache
from typing import List, Optional, Dict, Any

import polars as pl
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pyrox.manifest import load_manifest


class Settings(BaseSettings):
    pyrox_bucket: str = os.getenv("PYROX_BUCKET", "s3://hyrox-results")
    api_key: Optional[str] = os.getenv("PYROX_API_KEY")
    aws_region: str = os.getenv("AWS_REGION", "eu-west-1")


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
        return  ## dev mode: no auth
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
    m = _load_manifest_df()
    row = m[(m["season"] == season) & (m['location'].str.casefold() == location.casefold())]

    if row.empty:
        raise HTTPException(status_code=404, detail="No race for season={season}, location={location}")
    key = row.iloc[0]["path"]
    if key.startswith("s3://"):
        return key
    return f"s3://{bucket.rstrip('/')}/{key.lstrip('/')}"


#   Schemas

class ManifestRow(BaseModel):
    season: int
    location: str
    path: str


#   FastAPI app

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


@app.get("/v1/race/{season}/{location}")
def get_race(season: int, location: str, sex: Optional[str] = Query(default=None, description="Filter by sex"),
             division: Optional[str] = Query(default=None, description="Open / Pro"),
             settings: Settings = Depends(get_settings)):
    """
    Return filtered race
    :param season:
    :param location:
    :param sex:
    :param division:
    :return:
    """
    s3_uri = _s3_uri_for(season, location, settings.pyrox_bucket)

    opts = {"anon": True}

    try:
        lf = pl.scan_parquet(s3_uri)
    except Exception as e:
        raise HTTPException(502, detail=f"S3 read failed: {type(e).__name__} : {e}")

    if sex:
        lf = lf.filter(pl.col("sex") == sex)
    if division:
        lf = lf.filter(pl.col("division") == division)

    df = lf.collect()
    return df.to_dicts()
