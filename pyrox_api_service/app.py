"""FastAPI adapter for the Pyrox reporting module.

This file owns HTTP-specific concerns only: route declarations, request
parameter metadata, CORS, request logging, and conversion from query/runtime
errors to HTTP responses. Race, Result, Cohort, Distribution, and Athlete
Profile behaviour lives in ``pyrox_api_service.reporting_queries``.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

try:  # Prefer installed package imports.
    from pyrox.errors import AthleteNotFound
except ModuleNotFoundError:  # pragma: no cover - direct repository execution fallback
    from src.pyrox.errors import AthleteNotFound

from pyrox_api_service.database import DatabaseConfigurationError
from pyrox_api_service.ratelimit import RateLimitMiddleware
from pyrox_api_service.reporting_queries import (
    DISTRIBUTION_SMALL_SAMPLE_MIN_N as DISTRIBUTION_SMALL_SAMPLE_MIN_N,
    SEGMENT_CONFIG as SEGMENT_CONFIG,
    ReportingQueries,
    ReportingQueryError,
)


DEFAULT_ORIGINS = "http://localhost:5173,capacitor://localhost,ionic://localhost,http://localhost"


def _parse_origins(value: str) -> list[str]:
    """Parse a comma-separated CORS origin allow-list."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _raise_http(exc: Exception) -> None:
    """Map expected query/runtime exceptions to FastAPI HTTP errors."""
    if isinstance(exc, DatabaseConfigurationError):
        # Log the real cause (it contains the DuckDB path); return a generic
        # message so the filesystem layout is not leaked to clients.
        logger.error("database configuration error: %s", exc)
        raise HTTPException(status_code=500, detail="internal server error") from exc
    if isinstance(exc, AthleteNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ReportingQueryError):
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


def _query(call, *args, **kwargs):
    """Run a query-module callable and apply HTTP error mapping."""
    try:
        return call(*args, **kwargs)
    except Exception as exc:
        _raise_http(exc)


app = FastAPI(title="Pyrox Reporting API", version="0.1.0")
queries = ReportingQueries()
allowed_origins = _parse_origins(os.getenv("PYROX_API_ALLOW_ORIGINS", DEFAULT_ORIGINS))
# Added before CORS so a 429 still flows back out through CORSMiddleware and
# carries the Access-Control headers a browser client needs to read it. The MCP
# mount is exempt here and limited at the sub-app boundary to avoid charging the
# /mcp -> /mcp/ redirect plus the served request.
app.add_middleware(RateLimitMiddleware, exempt_path_prefixes=("/mcp",))
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("pyrox.api")
logger.info("CORS allowed origins: %s", ", ".join(allowed_origins))


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log request method/path, status code, and elapsed request time."""
    start = time.perf_counter()
    logger.info("request %s %s", request.method, request.url.path)
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    logger.info(
        "response %s %s -> %s (%.3fs)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


@app.get("/api/health")
def healthcheck() -> dict:
    """Return basic service and DuckDB artifact health details."""
    try:
        return queries.healthcheck()
    except Exception as exc:  # pragma: no cover - defensive for runtime env issues
        logger.info("healthcheck failed: %s", exc)
        if isinstance(exc, DatabaseConfigurationError):
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/athletes/search")
def search_athlete_races(
    name: str = Query(..., min_length=1),
    match: str = Query("best"),
    gender: Optional[str] = Query(None),
    division: Optional[str] = Query(None),
    nationality: Optional[str] = Query(None),
    require_unique: bool = Query(True),
    limit: Optional[int] = Query(None, ge=1, le=5000),
) -> dict:
    """Search athlete Results by name and optional identity filters."""
    return _query(
        queries.search_athlete_races,
        name=name,
        match=match,
        gender=gender,
        division=division,
        nationality=nationality,
        require_unique=require_unique,
        limit=limit,
    )


@app.get("/api/filter-options")
def filter_options(
    season: Optional[int] = Query(None, ge=1),
    division: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
) -> dict:
    """Return available Cohort filter values for the selected scope."""
    return _query(
        queries.filter_options,
        season=season,
        division=division,
        gender=gender,
    )


@app.get("/api/races")
def list_races(
    season: Optional[int] = Query(None, ge=1),
    gender: Optional[str] = Query(None),
) -> dict:
    """Return distinct races with participant counts."""
    return _query(
        queries.list_races,
        season=season,
        gender=gender,
    )


@app.get("/api/race-summary")
def race_summary(
    season: int = Query(..., ge=1),
    location: str = Query(..., min_length=1),
    gender: Optional[str] = Query(None),
    division: Optional[str] = Query(None),
    age_group: Optional[str] = Query(None),
    top_percentile: Optional[float] = Query(None, gt=0, lt=100),
) -> dict:
    """Return summary statistics across all timing metrics for one race."""
    return _query(
        queries.race_summary,
        season=season,
        location=location,
        gender=gender,
        division=division,
        age_group=age_group,
        top_percentile=top_percentile,
    )


@app.get("/api/reports/{result_id}")
def report_for_result(
    result_id: str,
    cohort_time_window_min: Optional[float] = Query(5.0),
    split_name: Optional[str] = Query(None),
    include_cohort: bool = Query(False),
    cohort_limit: int = Query(200, ge=1, le=5000),
    include_cohort_splits: bool = Query(False),
    cohort_splits_limit: int = Query(500, ge=1, le=10000),
) -> dict:
    """Return the Race report payload for one Result."""
    return _query(
        queries.report_for_result,
        result_id=result_id,
        cohort_time_window_min=cohort_time_window_min,
        split_name=split_name,
        include_cohort=include_cohort,
        cohort_limit=cohort_limit,
        include_cohort_splits=include_cohort_splits,
        cohort_splits_limit=cohort_splits_limit,
    )


@app.get("/api/deepdive/filters")
def deepdive_filter_options(
    season: int = Query(..., ge=1),
    division: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
) -> dict:
    """Return Deepdive filter options for one season."""
    return _query(
        queries.deepdive_filter_options,
        season=season,
        division=division,
        gender=gender,
    )


@app.get("/api/deepdive/{result_id}")
def deepdive_location_report(
    result_id: str,
    season: int = Query(..., ge=1),
    metric: str = Query("total_time_min"),
    bins: int = Query(22, ge=5, le=80),
    division: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    age_group: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
) -> dict:
    """Return a cross-location Deepdive report for one Result."""
    return _query(
        queries.deepdive_location_report,
        result_id=result_id,
        season=season,
        metric=metric,
        bins=bins,
        division=division,
        gender=gender,
        age_group=age_group,
        location=location,
    )


@app.get("/api/planner")
def planner_summary(
    season: Optional[int] = Query(None),
    location: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    division: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    min_total_time: Optional[float] = Query(None),
    max_total_time: Optional[float] = Query(None),
    bins: int = Query(22, ge=5, le=80),
) -> dict:
    """Return planner Segment distributions for the selected filters."""
    return _query(
        queries.planner_summary,
        season=season,
        location=location,
        year=year,
        division=division,
        gender=gender,
        min_total_time=min_total_time,
        max_total_time=max_total_time,
        bins=bins,
    )


@app.get("/api/distribution")
def distribution(
    gender: str = Query(..., min_length=1),
    season: Optional[int] = Query(None, ge=1),
    division: Optional[str] = Query(None),
    age_group: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    metric: str = Query("overall"),
    bins: int = Query(22, ge=5, le=80),
) -> dict:
    """Return a Cohort Distribution for one metric."""
    return _query(
        queries.distribution,
        gender=gender,
        season=season,
        division=division,
        age_group=age_group,
        location=location,
        metric=metric,
        bins=bins,
    )


@app.get("/api/rankings/filters")
def rankings_filter_options(
    season: int = Query(..., ge=1),
    division: str = Query(..., min_length=1),
    gender: str = Query(..., min_length=1),
    age_group: Optional[str] = Query(None),
) -> dict:
    """Return filter values for a Rankings Cohort."""
    return _query(
        queries.rankings_filter_options,
        season=season,
        division=division,
        gender=gender,
        age_group=age_group,
    )


@app.get("/api/rankings")
def rankings(
    season: int = Query(..., ge=1),
    division: str = Query(..., min_length=1),
    gender: str = Query(..., min_length=1),
    age_group: Optional[str] = Query(None),
    athlete_name: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    target_time_min: Optional[float] = Query(None, gt=0),
) -> dict:
    """Return ranked Results for a season, Division, and gender Cohort."""
    return _query(
        queries.rankings,
        season=season,
        division=division,
        gender=gender,
        age_group=age_group,
        athlete_name=athlete_name,
        limit=limit,
        target_time_min=target_time_min,
    )


@app.get("/api/athletes/{athlete_id}/profile")
def athlete_profile_by_id(
    athlete_id: str,
    division: Optional[str] = Query(None),
) -> dict:
    """Return an Athlete Profile by athlete id."""
    return _query(
        queries.athlete_profile_by_id,
        athlete_id=athlete_id,
        division=division,
    )


@app.get("/api/athletes/profile")
def athlete_profile(
    name: str = Query(..., min_length=1),
    division: Optional[str] = Query(None),
) -> dict:
    """Return an Athlete Profile by exact athlete name."""
    return _query(
        queries.athlete_profile_by_name,
        name=name,
        division=division,
    )
