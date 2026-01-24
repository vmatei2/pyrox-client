from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ..errors import AthleteNotFound
from ..reporting import ReportingClient

DEFAULT_DB_PATH = "pyrox_duckdb"
DEFAULT_ORIGINS = "http://localhost:5173"


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
    include_cohort: bool = Query(False),
    cohort_limit: int = Query(200, ge=1, le=5000),
    include_cohort_splits: bool = Query(False),
    cohort_splits_limit: int = Query(500, ge=1, le=10000),
) -> dict:
    reporting = _get_reporting()
    if cohort_time_window_min is not None and cohort_time_window_min <= 0:
        cohort_time_window_min = None
    try:
        report = reporting.race_report(
            result_id,
            cohort_time_window_min=cohort_time_window_min,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    race_rows = _df_to_records(report["race"], limit=1)
    race = race_rows[0] if race_rows else {}
    splits = _df_to_records(report["splits"])

    payload = {
        "result_id": result_id,
        "race": race,
        "splits": splits,
        "cohort_time_window_min": cohort_time_window_min,
        "cohort_stats": _describe_times(report["cohort"]),
        "cohort_time_window_stats": _describe_times(
            report.get("cohort_time_window", pd.DataFrame())
        ),
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

    return payload
