from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

try:  # Prefer installed package imports.
    from pyrox.errors import AthleteNotFound
    from pyrox.reporting import ReportingClient
except ModuleNotFoundError:  # Fallback for direct repository execution without installation.
    from src.pyrox.errors import AthleteNotFound
    from src.pyrox.reporting import ReportingClient

DEFAULT_DB_PATH = "pyrox_duckdb"
DEFAULT_ORIGINS = "http://localhost:5173,capacitor://localhost,ionic://localhost,http://localhost"
SEGMENT_CONFIG = [
    {"key": "total_time_min", "label": "Total time", "group": "overall"},
    {"key": "run1_time_min", "label": "Run 1", "group": "runs"},
    {"key": "run2_time_min", "label": "Run 2", "group": "runs"},
    {"key": "run3_time_min", "label": "Run 3", "group": "runs"},
    {"key": "run4_time_min", "label": "Run 4", "group": "runs"},
    {"key": "run5_time_min", "label": "Run 5", "group": "runs"},
    {"key": "run6_time_min", "label": "Run 6", "group": "runs"},
    {"key": "run7_time_min", "label": "Run 7", "group": "runs"},
    {"key": "run8_time_min", "label": "Run 8", "group": "runs"},
    {"key": "skiErg_time_min", "label": "SkiErg", "group": "stations"},
    {"key": "sledPush_time_min", "label": "Sled Push", "group": "stations"},
    {"key": "sledPull_time_min", "label": "Sled Pull", "group": "stations"},
    {"key": "burpeeBroadJump_time_min", "label": "Burpee Broad Jump", "group": "stations"},
    {"key": "rowErg_time_min", "label": "RowErg", "group": "stations"},
    {"key": "farmersCarry_time_min", "label": "Farmers Carry", "group": "stations"},
    {"key": "sandbagLunges_time_min", "label": "Sandbag Lunges", "group": "stations"},
    {"key": "wallBalls_time_min", "label": "Wall Balls", "group": "stations"},
]


def _parse_origins(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_db_path() -> str:
    raw = os.getenv("PYROX_DUCKDB_PATH", DEFAULT_DB_PATH)
    if raw == ":memory:":
        return raw
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                f"DuckDB file not found at '{path}'. "
                "Set PYROX_DUCKDB_PATH to a valid path."
            ),
        )
    return str(path)


def _get_reporting() -> ReportingClient:
    db_path = _resolve_db_path()
    return ReportingClient(database=db_path)


def _df_to_records(df: pd.DataFrame, limit: Optional[int] = None) -> list[dict]:
    if limit is not None:
        df = df.head(limit)
    if df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _describe_times(
    df: pd.DataFrame, column: str = "total_time_min"
) -> Optional[dict]:
    if column not in df.columns:
        return None
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    if values.empty:
        return None
    return {
        "count": int(values.shape[0]),
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "p10": float(values.quantile(0.1)),
        "p90": float(values.quantile(0.9)),
    }


def _describe_series(values: pd.Series, min_value: Optional[float] = None) -> Optional[dict]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if min_value is not None:
        clean = clean[clean >= min_value]
    if clean.empty:
        return None
    return {
        "count": int(clean.shape[0]),
        "min": float(clean.min()),
        "max": float(clean.max()),
        "mean": float(clean.mean()),
        "median": float(clean.median()),
        "p10": float(clean.quantile(0.1)),
        "p90": float(clean.quantile(0.9)),
    }


def _build_histogram(
    values: pd.Series,
    *,
    bins: int = 22,
    athlete_value: Optional[float] = None,
    min_value: Optional[float] = None,
) -> Optional[dict]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if min_value is not None:
        clean = clean[clean >= min_value]
    if clean.empty:
        return None
    athlete_percentile = None
    if athlete_value is not None:
        try:
            athlete_value = float(athlete_value)
        except (TypeError, ValueError):
            athlete_value = None
    if min_value is not None and athlete_value is not None and athlete_value < min_value:
        athlete_value = None
    if athlete_value is not None:
        if clean.shape[0] == 1:
            athlete_percentile = 1.0
        else:
            rank = int((clean < athlete_value).sum()) + 1
            athlete_percentile = 1.0 - (rank - 1) / (clean.shape[0] - 1)
    min_val = float(clean.min())
    max_val = float(clean.max())
    if min_val == max_val:
        max_val = min_val + 1.0
    counts, edges = np.histogram(clean.to_numpy(), bins=bins, range=(min_val, max_val))
    buckets = [
        {
            "start": float(edges[index]),
            "end": float(edges[index + 1]),
            "count": int(counts[index]),
        }
        for index in range(len(counts))
    ]
    return {
        "bins": buckets,
        "min": min_val,
        "max": max_val,
        "count": int(clean.shape[0]),
        "athlete_value": athlete_value,
        "athlete_percentile": athlete_percentile,
    }


def _min_value_for_segment(key: str) -> Optional[float]:
    if key.startswith("run") and key.endswith("_time_min"):
        return 1.0
    return None


def _min_value_for_split(split_name: str) -> Optional[float]:
    if split_name.casefold().startswith("run"):
        return 1.0
    return None


def _to_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


def _normalize_split_key(value: object) -> str:
    if value is None:
        return ""
    return "".join(ch for ch in str(value).strip().casefold() if ch.isalnum())


def _build_split_time_map(splits: pd.DataFrame) -> dict[str, float]:
    if (
        splits.empty
        or "split_name" not in splits.columns
        or "split_time_min" not in splits.columns
    ):
        return {}
    split_time_map: dict[str, float] = {}
    for _, row in splits.iterrows():
        key = _normalize_split_key(row.get("split_name"))
        value = _to_float(row.get("split_time_min"))
        if key and value is not None:
            split_time_map[key] = value
    return split_time_map


def _resolve_run_time(
    race: dict,
    split_time_map: dict[str, float],
    run_number: int,
) -> Optional[float]:
    column_value = _to_float(race.get(f"run{run_number}_time_min"))
    if column_value is not None:
        return column_value
    return split_time_map.get(f"run{run_number}")


def _build_work_vs_run_split(race: dict) -> Optional[dict]:
    work_time = _to_float(race.get("work_time_min"))
    run_time = _to_float(race.get("run_time_min"))
    roxzone_time = _to_float(race.get("roxzone_time_min"))

    if work_time is None and run_time is None and roxzone_time is None:
        return None

    run_with_roxzone = None
    if run_time is not None and roxzone_time is not None:
        run_with_roxzone = run_time + roxzone_time
    elif run_time is not None:
        run_with_roxzone = run_time
    elif roxzone_time is not None:
        run_with_roxzone = roxzone_time

    total_time = None
    work_pct = None
    run_pct = None
    if work_time is not None and run_with_roxzone is not None:
        total_time = work_time + run_with_roxzone
        if total_time > 0:
            work_pct = work_time / total_time
            run_pct = run_with_roxzone / total_time

    return {
        "work_time_min": work_time,
        "run_time_min": run_time,
        "roxzone_time_min": roxzone_time,
        "run_time_with_roxzone_min": run_with_roxzone,
        "total_time_min": total_time,
        "work_pct": work_pct,
        "run_pct": run_pct,
    }


def _build_run_change_series(race: dict, splits: pd.DataFrame) -> dict:
    split_time_map = _build_split_time_map(splits)
    points = []
    run_values: list[float] = []
    resolved_runs: dict[int, Optional[float]] = {}

    for run_number in range(2, 8):
        current_time = _resolve_run_time(race, split_time_map, run_number)
        resolved_runs[run_number] = current_time
        if current_time is not None:
            run_values.append(current_time)

    median_run_time = float(np.median(run_values)) if run_values else None
    deltas: list[float] = []

    for run_number in range(2, 8):
        current_time = resolved_runs.get(run_number)
        delta_from_median = None
        if current_time is not None and median_run_time is not None:
            delta_from_median = current_time - median_run_time
            deltas.append(delta_from_median)
        points.append(
            {
                "run": f"Run {run_number}",
                "run_time_min": current_time,
                "median_run_time_min": median_run_time,
                "delta_from_median_min": delta_from_median,
            }
        )

    return {
        "median_run_time_min": median_run_time,
        "points": points,
        "count": len(deltas),
        "min_delta_min": min(deltas) if deltas else None,
        "max_delta_min": max(deltas) if deltas else None,
    }


app = FastAPI(title="Pyrox Reporting API", version="0.1.0")
allowed_origins = _parse_origins(
    os.getenv("PYROX_API_ALLOW_ORIGINS", DEFAULT_ORIGINS)
)
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

# app.middleware is a decorator that runs this code on every incoming HTTP request!
@app.middleware("http")
async def log_requests(request: Request, call_next):
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
    db_path = _resolve_db_path()
    reporting = _get_reporting()
    try:
        con = reporting._ensure_connection()
        tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    except Exception as exc:  # pragma: no cover - defensive for runtime env issues
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", "database": db_path, "tables": tables}


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
    reporting = _get_reporting()
    try:
        logger.info("Starting search of athlete races")
        races = reporting.search_athlete_races(
            athlete_name=name,
            match=match,
            gender=gender,
            division=division,
            nationality=nationality,
            require_unique=require_unique,
        )
    except AthleteNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    total = int(len(races))
    logger.info(f"Have retrieved a total of {total} races")
    records = _df_to_records(races, limit=limit)
    return {
        "query": {
            "name": name,
            "match": match,
            "gender": gender,
            "division": division,
            "nationality": nationality,
            "require_unique": require_unique,
        },
        "count": len(records),
        "total": total,
        "races": records,
    }


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
    reporting = _get_reporting()
    start = time.perf_counter()
    logger.info("report start result_id=%s", result_id)
    if cohort_time_window_min is not None and cohort_time_window_min <= 0:
        cohort_time_window_min = None
    try:
        report = reporting.race_report(
            result_id,
            cohort_time_window_min=cohort_time_window_min,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("report data loaded in %.3fs", time.perf_counter() - start)

    race_rows = _df_to_records(report["race"], limit=1)
    race = race_rows[0] if race_rows else {}
    splits = _df_to_records(report["splits"])
    athlete_total_time = None
    if not report["race"].empty and "total_time_min" in report["race"].columns:
        value = report["race"]["total_time_min"].iloc[0]
        if value is not None and not pd.isna(value):
            athlete_total_time = float(value)

    cohort_hist = None
    if "total_time_min" in report["cohort"].columns:
        cohort_hist = _build_histogram(
            report["cohort"]["total_time_min"],
            athlete_value=athlete_total_time,
        )

    time_window_hist = None
    if "cohort_time_window" in report:
        cohort_window = report["cohort_time_window"]
        if "total_time_min" in cohort_window.columns:
            time_window_hist = _build_histogram(
                cohort_window["total_time_min"],
                athlete_value=athlete_total_time,
            )
    logger.info("report histograms built in %.3fs", time.perf_counter() - start)

    selected_split = None
    normalized_split = None
    if split_name is not None:
        normalized_split = str(split_name).strip()
        if normalized_split == "":
            normalized_split = None

    if normalized_split:
        split_key = normalized_split.casefold()
        split_min_value = _min_value_for_split(split_key)
        athlete_split_value = None
        if (
            "split_name" in report["splits"].columns
            and "split_time_min" in report["splits"].columns
        ):
            split_mask = (
                report["splits"]["split_name"].astype(str).str.casefold() == split_key
            )
            if split_mask.any():
                split_value = report["splits"].loc[split_mask, "split_time_min"].iloc[0]
                if split_value is not None and not pd.isna(split_value):
                    athlete_split_value = float(split_value)

        def build_split_hist(df: pd.DataFrame) -> Optional[dict]:
            if (
                df.empty
                or "split_name" not in df.columns
                or "split_time_min" not in df.columns
            ):
                return None
            mask = df["split_name"].astype(str).str.casefold() == split_key
            if not mask.any():
                return None
            return _build_histogram(
                df.loc[mask, "split_time_min"],
                athlete_value=athlete_split_value,
                min_value=split_min_value,
            )

        def build_split_stats(df: pd.DataFrame) -> Optional[dict]:
            if (
                df.empty
                or "split_name" not in df.columns
                or "split_time_min" not in df.columns
            ):
                return None
            mask = df["split_name"].astype(str).str.casefold() == split_key
            if not mask.any():
                return None
            return _describe_series(df.loc[mask, "split_time_min"], min_value=split_min_value)

        selected_split = {
            "name": normalized_split,
            "cohort": build_split_hist(report["cohort_splits"]),
            "time_window": build_split_hist(
                report.get("cohort_time_window_splits", pd.DataFrame())
            ),
            "stats": {
                "cohort": build_split_stats(report["cohort_splits"]),
                "time_window": build_split_stats(
                    report.get("cohort_time_window_splits", pd.DataFrame())
                ),
            },
        }
        logger.info("report split distributions built in %.3fs", time.perf_counter() - start)

    payload = {
        "result_id": result_id,
        "race": race,
        "splits": splits,
        "plot_data": {
            "work_vs_run_split": _build_work_vs_run_split(race),
            "run_change_series": _build_run_change_series(race, report["splits"]),
        },
        "cohort_time_window_min": cohort_time_window_min,
        "cohort_stats": _describe_times(report["cohort"]),
        "cohort_time_window_stats": _describe_times(
            report.get("cohort_time_window", pd.DataFrame())
        ),
        "distributions": {
            "cohort_total_time": cohort_hist,
            "time_window_total_time": time_window_hist,
            "selected_split": selected_split,
        },
    }

    if include_cohort:
        payload["cohort_preview"] = {
            "columns": list(report["cohort"].columns),
            "rows": _df_to_records(report["cohort"], limit=cohort_limit),
            "total": int(len(report["cohort"])),
        }
    if include_cohort_splits:
        payload["cohort_splits_preview"] = {
            "columns": list(report["cohort_splits"].columns),
            "rows": _df_to_records(
                report["cohort_splits"],
                limit=cohort_splits_limit,
            ),
            "total": int(len(report["cohort_splits"])),
        }
        if "cohort_time_window_splits" in report:
            payload["cohort_time_window_splits_preview"] = {
                "columns": list(report["cohort_time_window_splits"].columns),
                "rows": _df_to_records(
                    report["cohort_time_window_splits"],
                    limit=cohort_splits_limit,
                ),
                "total": int(len(report["cohort_time_window_splits"])),
            }

    logger.info("report response ready in %.3fs", time.perf_counter() - start)
    return payload


@app.get("/api/deepdive/filters")
def deepdive_filter_options(
    season: int = Query(..., ge=1),
    division: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
) -> dict:
    reporting = _get_reporting()
    start = time.perf_counter()
    logger.info("deepdive filters start season=%s", season)
    try:
        options = reporting.deepdive_filter_options(
            season=season,
            division=division,
            gender=gender,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = {
        "filters": {"season": season, "division": division, "gender": gender},
        "locations": options.get("locations", []),
        "age_groups": options.get("age_groups", []),
    }
    logger.info("deepdive filters ready in %.3fs", time.perf_counter() - start)
    return payload


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
    reporting = _get_reporting()
    start = time.perf_counter()
    logger.info("deepdive start result_id=%s", result_id)
    try:
        report = reporting.deepdive_location_stats(
            result_id,
            season=season,
            metric=metric,
            bins=bins,
            division=division,
            gender=gender,
            age_group=age_group,
            location=location,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    race_rows = _df_to_records(report["race"], limit=1)
    race = race_rows[0] if race_rows else {}
    locations = _df_to_records(report["locations"])
    payload = {
        "result_id": result_id,
        "race": race,
        "athlete_value": report["athlete_value"],
        "metric": report["metric"],
        "summary": report["summary"],
        "group_summary": report.get("group_summary"),
        "distribution": report.get("distribution"),
        "group_distribution": report.get("group_distribution"),
        "filters": report["filters"],
        "total_rows": report["total_rows"],
        "total_locations": report["total_locations"],
        "locations": locations,
    }
    logger.info("deepdive response ready in %.3fs", time.perf_counter() - start)
    return payload


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
    if min_total_time is not None and max_total_time is not None:
        if min_total_time > max_total_time:
            raise HTTPException(
                status_code=400,
                detail="min_total_time must be less than or equal to max_total_time.",
            )

    clauses = []
    params: list[object] = []
    if season is not None:
        clauses.append("season = ?")
        params.append(int(season))
    if location is not None and str(location).strip() != "":
        clauses.append("lower(location) = ?")
        params.append(str(location).strip().casefold())
    if year is not None:
        clauses.append("year = ?")
        params.append(int(year))
    if division is not None and str(division).strip() != "":
        clauses.append("lower(division) = ?")
        params.append(str(division).strip().casefold())
    if gender is not None and str(gender).strip() != "":
        normalized_gender = str(gender).strip().casefold()
        if normalized_gender in {"m", "male"}:
            clauses.append("lower(gender) IN (?, ?)")
            params.extend(["m", "male"])
        elif normalized_gender in {"f", "female"}:
            clauses.append("lower(gender) IN (?, ?)")
            params.extend(["f", "female"])
        else:
            clauses.append("lower(gender) = ?")
            params.append(normalized_gender)
    if min_total_time is not None:
        clauses.append("total_time_min >= ?")
        params.append(float(min_total_time))
    if max_total_time is not None:
        clauses.append("total_time_min <= ?")
        params.append(float(max_total_time))

    columns = [config["key"] for config in SEGMENT_CONFIG]
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT {', '.join(columns)} FROM race_results {where_sql}"

    reporting = _get_reporting()
    con = reporting._ensure_connection()
    df = con.execute(sql, params).fetchdf()

    segments = []
    for config in SEGMENT_CONFIG:
        key = config["key"]
        if key not in df.columns:
            continue
        min_value = _min_value_for_segment(key)
        histogram = _build_histogram(df[key], bins=bins, min_value=min_value)
        if histogram is None:
            continue
        segments.append(
            {
                "key": key,
                "label": config["label"],
                "group": config["group"],
                "histogram": histogram,
                "stats": _describe_series(df[key], min_value=min_value),
            }
        )

    return {
        "filters": {
            "season": season,
            "location": location,
            "year": year,
            "division": division,
            "gender": gender,
            "min_total_time": min_total_time,
            "max_total_time": max_total_time,
        },
        "count": int(len(df)),
        "segments": segments,
    }
