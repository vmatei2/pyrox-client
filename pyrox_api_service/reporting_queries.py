"""Reporting query module behind the FastAPI adapter.

The functions in this module speak in Race, Result, Cohort, Distribution, and
Athlete Profile terms. HTTP routing, request validation, and HTTP error mapping
stay in ``app.py``; this module owns the query shapes and response payloads used
by the REST and MCP-facing adapters.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

import numpy as np
import pandas as pd

from pyrox_api_service.database import DuckDBRuntime, get_runtime


logger = logging.getLogger("pyrox.api")

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

_PROFILE_TIME_COLUMN_MAP = {
    "overall": "total_time_min",
    "skierg": "skiErg_time_min",
    "sledpush": "sledPush_time_min",
    "sledpull": "sledPull_time_min",
    "burpeebroadjump": "burpeeBroadJump_time_min",
    "rowerg": "rowErg_time_min",
    "farmerscarry": "farmersCarry_time_min",
    "sandbaglunges": "sandbagLunges_time_min",
    "wallballs": "wallBalls_time_min",
}

DISTRIBUTION_SMALL_SAMPLE_MIN_N = 30
_DISTRIBUTION_METRIC_COLUMN_MAP = {
    **_PROFILE_TIME_COLUMN_MAP,
    **{f"run{number}": f"run{number}_time_min" for number in range(1, 9)},
}

_PROFILE_RUN_ROXZONE_KEY = "runplusroxzone"
_PROFILE_PERCENTILE_COHORT_COLUMNS = {"division", "gender"}
_PROFILE_RACE_PROGRESS_COLUMNS = (
    "total_time_min",
    "run_time_min",
    "work_time_min",
    "roxzone_time_min",
    "run1_time_min",
    "run2_time_min",
    "run3_time_min",
    "run4_time_min",
    "run5_time_min",
    "run6_time_min",
    "run7_time_min",
    "run8_time_min",
    "skiErg_time_min",
    "sledPush_time_min",
    "sledPull_time_min",
    "burpeeBroadJump_time_min",
    "rowErg_time_min",
    "farmersCarry_time_min",
    "sandbagLunges_time_min",
    "wallBalls_time_min",
)


class ReportingQueryError(ValueError):
    """Base error for expected query failures that map to a client error."""

    status_code = 400


class ReportingNotFoundError(ReportingQueryError):
    """Raised when a requested Result, Race, or Athlete Profile is absent."""

    status_code = 404


class ReportingConflictError(ReportingQueryError):
    """Raised when a request is valid but needs caller-side disambiguation."""

    status_code = 409


def df_to_records(df: pd.DataFrame, limit: Optional[int] = None) -> list[dict]:
    """Convert a DataFrame to JSON-ready records.

    Args:
        df: Source DataFrame, typically returned from DuckDB.
        limit: Optional maximum number of rows to include from the head.

    Returns:
        A list of dictionaries with timestamp/date values encoded using pandas'
        ISO JSON conversion. Empty DataFrames return an empty list.
    """
    if limit is not None:
        df = df.head(limit)
    if df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


def normalize_optional_text(value: Optional[str]) -> Optional[str]:
    """Normalize optional text filters to either stripped text or ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _normalize_profile_division_filter(value: Optional[str]) -> Optional[str]:
    """Normalize the optional Division filter used by Athlete Profile queries."""
    return normalize_optional_text(value)


def _load_race_results_columns(con) -> set[str]:
    """Return the column names currently present on ``race_results``.

    Some fixture databases and older artifacts do not carry every derived
    column. Profile code uses this to decide whether fallback calculations are
    possible instead of failing on missing columns.
    """
    return {
        str(row[1])
        for row in con.execute("PRAGMA table_info('race_results')").fetchall()
        if row and len(row) > 1
    }


def _clean_distinct_values(df: pd.DataFrame, column: str) -> list[str]:
    """Return sorted, non-empty string values from one DataFrame column."""
    if df.empty or column not in df.columns:
        return []
    values = (
        df[column]
        .dropna()
        .astype(str)
        .map(str.strip)
        .loc[lambda series: series != ""]
        .unique()
        .tolist()
    )
    return sorted(values, key=lambda value: value.casefold())


def _clean_distinct_numbers(
    df: pd.DataFrame,
    column: str,
    *,
    descending: bool = False,
) -> list[int]:
    """Return sorted integer values from one DataFrame column.

    Non-numeric values are ignored. This is used for filter metadata where stale
    or partial database artifacts should not make the whole response fail.
    """
    if df.empty or column not in df.columns:
        return []
    numbers: set[int] = set()
    for value in df[column].dropna().tolist():
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        numbers.add(number)
    return sorted(numbers, reverse=descending)


def _describe_times(df: pd.DataFrame, column: str = "total_time_min") -> Optional[dict]:
    """Describe a time column using count and common summary statistics."""
    if column not in df.columns:
        return None
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    if values.empty:
        return None
    return _describe_clean_series(values)


def _describe_clean_series(values: pd.Series) -> dict:
    """Return summary statistics for an already-clean numeric series."""
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
    """Coerce, optionally floor-filter, and describe a numeric series."""
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if min_value is not None:
        clean = clean[clean >= min_value]
    if clean.empty:
        return None
    return _describe_clean_series(clean)


def _build_histogram(
    values: pd.Series,
    *,
    bins: int = 22,
    athlete_value: Optional[float] = None,
    min_value: Optional[float] = None,
) -> Optional[dict]:
    """Build histogram buckets and an optional athlete percentile.

    Args:
        values: Raw metric values, usually in minutes.
        bins: Number of histogram buckets.
        athlete_value: Optional value to place within the distribution.
        min_value: Optional lower bound for valid values. Run times use this to
            suppress parse artifacts below one minute.

    Returns:
        ``None`` when no valid values remain, otherwise a dictionary containing
        buckets, min/max, count, the optional athlete value, and its percentile.
    """
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
        {"start": float(edges[index]), "end": float(edges[index + 1]), "count": int(counts[index])}
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
    """Return the minimum plausible value for a Segment time column."""
    if key.startswith("run") and key.endswith("_time_min"):
        return 1.0
    return None


def _min_value_for_split(split_name: str) -> Optional[float]:
    """Return the minimum plausible value for a split name."""
    if split_name.casefold().startswith("run"):
        return 1.0
    return None


def _to_float(value: object) -> Optional[float]:
    """Convert a value to a finite float, returning ``None`` when invalid."""
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
    """Normalize Segment labels to an alphanumeric lowercase key."""
    if value is None:
        return ""
    return "".join(ch for ch in str(value).strip().casefold() if ch.isalnum())


def _build_split_time_map(splits: pd.DataFrame) -> dict[str, float]:
    """Return a normalized split-name to split-time map from split rows."""
    if splits.empty or "split_name" not in splits.columns or "split_time_min" not in splits.columns:
        return {}
    split_time_map: dict[str, float] = {}
    for _, row in splits.iterrows():
        key = _normalize_split_key(row.get("split_name"))
        value = _to_float(row.get("split_time_min"))
        if key and value is not None:
            split_time_map[key] = value
    return split_time_map


def _resolve_run_time(race: dict, split_time_map: dict[str, float], run_number: int) -> Optional[float]:
    """Resolve a Run time from race columns, falling back to split rows."""
    column_value = _to_float(race.get(f"run{run_number}_time_min"))
    if column_value is not None:
        return column_value
    return split_time_map.get(f"run{run_number}")


def _build_work_vs_run_split(race: dict) -> Optional[dict]:
    """Build work-vs-run summary data for one Result.

    Returns ``None`` when the Result has no usable work, run, or Roxzone values.
    Otherwise the payload contains raw times plus work/run proportions where a
    positive combined total is available.
    """
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
    """Build Run 2-7 deviation data for the race-report line chart.

    The median is computed across available Run 2-7 values, using explicit race
    columns first and split rows as a fallback. Missing runs are represented with
    ``None`` values so chart callers keep a stable x-axis.
    """
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


def _resolve_distribution_metric(metric: str) -> tuple[str, str]:
    """Resolve a friendly Distribution metric key to a DuckDB column."""
    key = _normalize_split_key(metric)
    column = _DISTRIBUTION_METRIC_COLUMN_MAP.get(key)
    if column is None:
        raise ReportingQueryError(f"Unknown metric '{metric}'.")
    return column, key


class ReportingQueries:
    """Deep query module used by REST and MCP-facing adapters.

    Args:
        runtime: Optional DuckDB runtime. Tests can pass an explicit runtime;
            request handling normally resolves it from environment variables.

    The public methods return JSON-ready dictionaries matching the existing
    endpoint payloads. They raise ``ReportingQueryError`` subclasses for
    expected caller-facing failures and let unexpected database/runtime failures
    bubble to the adapter.
    """

    def __init__(self, runtime: Optional[DuckDBRuntime] = None) -> None:
        """Store an optional runtime for direct tests or explicit wiring."""
        self._runtime = runtime

    def runtime(self) -> DuckDBRuntime:
        """Return the configured runtime, resolving from the environment lazily."""
        return self._runtime or get_runtime()

    def reporting(self):
        """Return a ``ReportingClient`` for higher-level reporting queries."""
        return self.runtime().reporting_client()

    def connection(self):
        """Return a DuckDB connection for query paths not yet in ``ReportingClient``."""
        return self.runtime().connection()

    def healthcheck(self) -> dict:
        """Return service health details for the configured DuckDB artifact.

        Output shape:
            ``{"status": "ok", "database": <path>, "tables": [<name>, ...]}``.
        """
        runtime = self.runtime()
        return {
            "status": "ok",
            "database": runtime.database_path,
            "tables": runtime.list_tables(),
        }

    def search_athlete_races(
        self,
        *,
        name: str,
        match: str = "best",
        gender: Optional[str] = None,
        division: Optional[str] = None,
        nationality: Optional[str] = None,
        require_unique: bool = True,
        limit: Optional[int] = None,
    ) -> dict:
        """Search Results for an athlete name and return a capped race list.

        Args:
            name: Athlete name to search.
            match: Search mode accepted by ``ReportingClient``.
            gender: Optional Athlete/Result gender filter.
            division: Optional Division filter.
            nationality: Optional Athlete nationality filter.
            require_unique: Whether ambiguous athlete matches should fail.
            limit: Optional number of returned races; ``total`` still reports
                all matches.

        Returns:
            A JSON-ready payload with the query echo, returned count, total
            matches, and matching race records.
        """
        races = self.reporting().search_athlete_races(
            athlete_name=name,
            match=match,
            gender=gender,
            division=division,
            nationality=nationality,
            require_unique=require_unique,
        )
        total = int(len(races))
        records = df_to_records(races, limit=limit)
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

    def filter_options(
        self,
        *,
        season: Optional[int] = None,
        division: Optional[str] = None,
        gender: Optional[str] = None,
    ) -> dict:
        """Return available Cohort filter values for the current database.

        Optional season, Division, and gender filters scope the distinct values.
        Gender accepts both abbreviated and full values, with ``M``/``male`` and
        ``F``/``female`` treated as equivalent.
        """
        con = self.connection()
        clauses = []
        params: list[object] = []
        if season is not None:
            clauses.append("season = ?")
            params.append(int(season))

        normalized_division = normalize_optional_text(division)
        if normalized_division is not None:
            clauses.append("lower(division) = ?")
            params.append(normalized_division.casefold())

        normalized_gender = normalize_optional_text(gender)
        if normalized_gender is not None:
            normalized_gender_key = normalized_gender.casefold()
            if normalized_gender_key in {"m", "male"}:
                clauses.append("lower(gender) IN (?, ?)")
                params.extend(["m", "male"])
            elif normalized_gender_key in {"f", "female"}:
                clauses.append("lower(gender) IN (?, ?)")
                params.extend(["f", "female"])
            else:
                clauses.append("lower(gender) = ?")
                params.append(normalized_gender_key)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        seasons_df = con.execute(f"SELECT DISTINCT season FROM race_results {where_sql}", params).fetchdf()
        years_df = con.execute(f"SELECT DISTINCT year FROM race_results {where_sql}", params).fetchdf()
        divisions_df = con.execute(f"SELECT DISTINCT division FROM race_results {where_sql}", params).fetchdf()
        genders_df = con.execute(f"SELECT DISTINCT gender FROM race_results {where_sql}", params).fetchdf()
        locations_df = con.execute(f"SELECT DISTINCT location FROM race_results {where_sql}", params).fetchdf()
        age_groups_df = con.execute(f"SELECT DISTINCT age_group FROM race_results {where_sql}", params).fetchdf()

        return {
            "filters": {"season": season, "division": normalized_division, "gender": normalized_gender},
            "seasons": _clean_distinct_numbers(seasons_df, "season", descending=True),
            "years": _clean_distinct_numbers(years_df, "year", descending=True),
            "divisions": _clean_distinct_values(divisions_df, "division"),
            "genders": _clean_distinct_values(genders_df, "gender"),
            "locations": _clean_distinct_values(locations_df, "location"),
            "age_groups": _clean_distinct_values(age_groups_df, "age_group"),
        }

    def report_for_result(
        self,
        *,
        result_id: str,
        cohort_time_window_min: Optional[float] = 5.0,
        split_name: Optional[str] = None,
        include_cohort: bool = False,
        cohort_limit: int = 200,
        include_cohort_splits: bool = False,
        cohort_splits_limit: int = 500,
    ) -> dict:
        """Build the Race report payload for one Result.

        Args:
            result_id: Result identifier.
            cohort_time_window_min: Optional +/- finish-time window for the
                comparison cohort. Non-positive values disable the window.
            split_name: Optional Segment to include selected-split distribution
                data for.
            include_cohort: Whether to include a capped cohort preview.
            cohort_limit: Maximum preview rows when ``include_cohort`` is true.
            include_cohort_splits: Whether to include a capped split preview.
            cohort_splits_limit: Maximum preview rows for split previews.

        Returns:
            A JSON-ready Race report containing the selected Result, split rows,
            chart data, summary stats, and Distribution payloads.
        """
        start = time.perf_counter()
        if cohort_time_window_min is not None and cohort_time_window_min <= 0:
            cohort_time_window_min = None
        report = self.reporting().race_report(
            result_id,
            cohort_time_window_min=cohort_time_window_min,
        )

        race_rows = df_to_records(report["race"], limit=1)
        race = race_rows[0] if race_rows else {}
        splits = df_to_records(report["splits"])
        athlete_total_time = None
        if not report["race"].empty and "total_time_min" in report["race"].columns:
            value = report["race"]["total_time_min"].iloc[0]
            if value is not None and not pd.isna(value):
                athlete_total_time = float(value)

        cohort_hist = None
        if "total_time_min" in report["cohort"].columns:
            cohort_hist = _build_histogram(report["cohort"]["total_time_min"], athlete_value=athlete_total_time)

        time_window_hist = None
        if "cohort_time_window" in report:
            cohort_window = report["cohort_time_window"]
            if "total_time_min" in cohort_window.columns:
                time_window_hist = _build_histogram(
                    cohort_window["total_time_min"],
                    athlete_value=athlete_total_time,
                )

        selected_split = None
        normalized_split = normalize_optional_text(split_name)
        if normalized_split:
            split_key = normalized_split.casefold()
            split_min_value = _min_value_for_split(split_key)
            athlete_split_value = None
            if "split_name" in report["splits"].columns and "split_time_min" in report["splits"].columns:
                split_mask = report["splits"]["split_name"].astype(str).str.casefold() == split_key
                if split_mask.any():
                    split_value = report["splits"].loc[split_mask, "split_time_min"].iloc[0]
                    if split_value is not None and not pd.isna(split_value):
                        athlete_split_value = float(split_value)

            def build_split_hist(df: pd.DataFrame) -> Optional[dict]:
                """Build selected-split histogram data from split rows."""
                if df.empty or "split_name" not in df.columns or "split_time_min" not in df.columns:
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
                """Build selected-split summary stats from split rows."""
                if df.empty or "split_name" not in df.columns or "split_time_min" not in df.columns:
                    return None
                mask = df["split_name"].astype(str).str.casefold() == split_key
                if not mask.any():
                    return None
                return _describe_series(df.loc[mask, "split_time_min"], min_value=split_min_value)

            selected_split = {
                "name": normalized_split,
                "cohort": build_split_hist(report["cohort_splits"]),
                "time_window": build_split_hist(report.get("cohort_time_window_splits", pd.DataFrame())),
                "stats": {
                    "cohort": build_split_stats(report["cohort_splits"]),
                    "time_window": build_split_stats(
                        report.get("cohort_time_window_splits", pd.DataFrame())
                    ),
                },
            }

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
                "rows": df_to_records(report["cohort"], limit=cohort_limit),
                "total": int(len(report["cohort"])),
            }
        if include_cohort_splits:
            payload["cohort_splits_preview"] = {
                "columns": list(report["cohort_splits"].columns),
                "rows": df_to_records(report["cohort_splits"], limit=cohort_splits_limit),
                "total": int(len(report["cohort_splits"])),
            }
            if "cohort_time_window_splits" in report:
                payload["cohort_time_window_splits_preview"] = {
                    "columns": list(report["cohort_time_window_splits"].columns),
                    "rows": df_to_records(
                        report["cohort_time_window_splits"],
                        limit=cohort_splits_limit,
                    ),
                    "total": int(len(report["cohort_time_window_splits"])),
                }

        logger.info("report response ready in %.3fs", time.perf_counter() - start)
        return payload

    def deepdive_filter_options(
        self,
        *,
        season: int,
        division: Optional[str] = None,
        gender: Optional[str] = None,
    ) -> dict:
        """Return Deepdive filter options for one season and optional Cohort scope."""
        options = self.reporting().deepdive_filter_options(
            season=season,
            division=division,
            gender=gender,
        )
        return {
            "filters": {"season": season, "division": division, "gender": gender},
            "locations": options.get("locations", []),
            "age_groups": options.get("age_groups", []),
        }

    def deepdive_location_report(
        self,
        *,
        result_id: str,
        season: int,
        metric: str = "total_time_min",
        bins: int = 22,
        division: Optional[str] = None,
        gender: Optional[str] = None,
        age_group: Optional[str] = None,
        location: Optional[str] = None,
    ) -> dict:
        """Build a cross-location Deepdive report for one Result.

        Season is required by design. Division, gender, age group, and location
        override the selected Result's default Cohort when provided.
        """
        report = self.reporting().deepdive_location_stats(
            result_id,
            season=season,
            metric=metric,
            bins=bins,
            division=division,
            gender=gender,
            age_group=age_group,
            location=location,
        )
        race_rows = df_to_records(report["race"], limit=1)
        return {
            "result_id": result_id,
            "race": race_rows[0] if race_rows else {},
            "athlete_value": report["athlete_value"],
            "metric": report["metric"],
            "summary": report["summary"],
            "group_summary": report.get("group_summary"),
            "distribution": report.get("distribution"),
            "group_distribution": report.get("group_distribution"),
            "filters": report["filters"],
            "total_rows": report["total_rows"],
            "total_locations": report["total_locations"],
            "locations": df_to_records(report["locations"]),
        }

    def planner_summary(
        self,
        *,
        season: Optional[int] = None,
        location: Optional[str] = None,
        year: Optional[int] = None,
        division: Optional[str] = None,
        gender: Optional[str] = None,
        min_total_time: Optional[float] = None,
        max_total_time: Optional[float] = None,
        bins: int = 22,
    ) -> dict:
        """Return Segment distributions for planner filters.

        The payload contains an echoed filter block, total matching Result
        count, and one histogram/stat block per Segment with usable data.
        """
        if min_total_time is not None and max_total_time is not None and min_total_time > max_total_time:
            raise ReportingQueryError("min_total_time must be less than or equal to max_total_time.")

        clauses = []
        params: list[object] = []
        if season is not None:
            clauses.append("season = ?")
            params.append(int(season))
        if normalize_optional_text(location) is not None:
            clauses.append("lower(location) = ?")
            params.append(str(location).strip().casefold())
        if year is not None:
            clauses.append("year = ?")
            params.append(int(year))
        if normalize_optional_text(division) is not None:
            clauses.append("lower(division) = ?")
            params.append(str(division).strip().casefold())
        if normalize_optional_text(gender) is not None:
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
        df = self.connection().execute(sql, params).fetchdf()

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

    def distribution(
        self,
        *,
        gender: str,
        season: Optional[int] = None,
        division: Optional[str] = None,
        age_group: Optional[str] = None,
        location: Optional[str] = None,
        metric: str = "overall",
        bins: int = 22,
    ) -> dict:
        """Return a Cohort Distribution for one metric.

        Defaults match the documented MCP behaviour: Division defaults to
        ``open`` and season defaults to the latest season available for the
        filtered Cohort. Small Cohorts keep the histogram but suppress fragile
        percentile tails.
        """
        con = self.connection()
        column, metric_key = _resolve_distribution_metric(metric)
        normalized_division = normalize_optional_text(division) or "open"
        normalized_gender = str(gender).strip()

        clauses = ["lower(division) = ?"]
        params: list[object] = [normalized_division.casefold()]
        gender_key = normalized_gender.casefold()
        if gender_key in {"m", "male"}:
            clauses.append("lower(gender) IN (?, ?)")
            params.extend(["m", "male"])
        elif gender_key in {"f", "female"}:
            clauses.append("lower(gender) IN (?, ?)")
            params.extend(["f", "female"])
        else:
            clauses.append("lower(gender) = ?")
            params.append(gender_key)

        normalized_age_group = normalize_optional_text(age_group)
        if normalized_age_group is not None:
            clauses.append("lower(age_group) = ?")
            params.append(normalized_age_group.casefold())
        normalized_location = normalize_optional_text(location)
        if normalized_location is not None:
            clauses.append("lower(location) = ?")
            params.append(normalized_location.casefold())

        resolved_season = int(season) if season is not None else None
        if resolved_season is None:
            latest = con.execute(
                f"SELECT max(season) FROM race_results WHERE {' AND '.join(clauses)}",
                params,
            ).fetchone()
            resolved_season = int(latest[0]) if latest and latest[0] is not None else None
        if resolved_season is not None:
            clauses.append("season = ?")
            params.append(resolved_season)

        where_sql = " AND ".join(clauses)
        df = con.execute(f"SELECT {column} AS value FROM race_results WHERE {where_sql}", params).fetchdf()
        min_value = _min_value_for_segment(column)
        histogram = _build_histogram(df["value"], bins=bins, min_value=min_value)
        stats = _describe_series(df["value"], min_value=min_value)
        n = 0 if stats is None else int(stats["count"])

        small_sample = 0 < n < DISTRIBUTION_SMALL_SAMPLE_MIN_N
        note = None
        if small_sample and stats is not None:
            stats = {**stats, "p10": None, "p90": None}
            note = (
                f"Small cohort (n={n} < {DISTRIBUTION_SMALL_SAMPLE_MIN_N}): "
                "percentile tails are suppressed and estimates are unstable."
            )

        return {
            "metric": metric_key,
            "cohort": {
                "season": resolved_season,
                "division": normalized_division,
                "gender": normalized_gender,
                "age_group": normalized_age_group,
                "location": normalized_location,
            },
            "n": n,
            "small_sample": small_sample,
            "note": note,
            "histogram": histogram,
            "stats": stats,
        }

    def rankings_filter_options(
        self,
        *,
        season: int,
        division: str,
        gender: str,
        age_group: Optional[str] = None,
    ) -> dict:
        """Return age-group and location values for a Rankings Cohort."""
        con = self.connection()
        normalized_division = str(division).strip()
        if not normalized_division:
            raise ReportingQueryError("division is required for rankings filters.")
        normalized_gender = str(gender).strip()
        if not normalized_gender:
            raise ReportingQueryError("gender is required for rankings filters.")

        gender_clauses, gender_params = _gender_filter(normalized_gender)
        normalized_age_group = normalize_optional_text(age_group)
        age_group_clauses = ["season = ?", "lower(division) = ?", *gender_clauses]
        age_group_params: list[object] = [int(season), normalized_division.casefold(), *gender_params]
        if normalized_age_group is not None:
            age_group_clauses.append("lower(age_group) = ?")
            age_group_params.append(normalized_age_group.casefold())
        age_group_where_sql = " AND ".join(age_group_clauses)

        age_groups_df = con.execute(
            f"""
            SELECT DISTINCT age_group
            FROM race_results
            WHERE season = ?
              AND lower(division) = ?
              AND {' AND '.join(gender_clauses)}
            """,
            [int(season), normalized_division.casefold(), *gender_params],
        ).fetchdf()
        locations_df = con.execute(
            f"SELECT DISTINCT location FROM race_results WHERE {age_group_where_sql}",
            age_group_params,
        ).fetchdf()

        return {
            "filters": {
                "season": int(season),
                "division": normalized_division,
                "gender": normalized_gender,
                "age_group": normalized_age_group,
            },
            "age_groups": _clean_distinct_values(age_groups_df, "age_group"),
            "locations": _clean_distinct_values(locations_df, "location"),
        }

    def rankings(
        self,
        *,
        season: int,
        division: str,
        gender: str,
        age_group: Optional[str] = None,
        athlete_name: Optional[str] = None,
        limit: int = 200,
        target_time_min: Optional[float] = None,
    ) -> dict:
        """Return ranked Results for a season/Division/gender Cohort.

        The optional athlete-name filter is applied after placement is computed,
        so returned rows keep their global Cohort placement. ``target_time_min``
        reports where a hypothetical finish time would place.
        """
        con = self.connection()
        normalized_division = str(division).strip()
        if not normalized_division:
            raise ReportingQueryError("division is required for rankings.")
        normalized_gender = str(gender).strip()
        if not normalized_gender:
            raise ReportingQueryError("gender is required for rankings.")

        gender_clauses, gender_params = _gender_filter(normalized_gender)
        normalized_age_group = normalize_optional_text(age_group)
        normalized_athlete_name = normalize_optional_text(athlete_name)
        clauses = ["season = ?", "lower(division) = ?", *gender_clauses, "total_time_min IS NOT NULL"]
        params: list[object] = [int(season), normalized_division.casefold(), *gender_params]
        if normalized_age_group is not None:
            clauses.append("lower(age_group) = ?")
            params.append(normalized_age_group.casefold())
        where_sql = " AND ".join(clauses)

        total_rows = con.execute(f"SELECT COUNT(*) FROM race_results WHERE {where_sql}", params).fetchone()[0]
        ranked_where_sql = ""
        ranked_params: list[object] = []
        if normalized_athlete_name is not None:
            ranked_where_sql = "WHERE lower(name) LIKE ?"
            ranked_params.append(f"%{normalized_athlete_name.casefold()}%")

        ranking_rows = con.execute(
            f"""
            WITH base AS (
                SELECT *
                FROM race_results
                WHERE {where_sql}
            ),
            ranked AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY total_time_min ASC, result_id ASC) AS placement,
                    result_id,
                    name,
                    event_name,
                    event_id,
                    location,
                    season,
                    year,
                    division,
                    gender,
                    age_group,
                    total_time_min
                FROM base
            )
            SELECT *
            FROM ranked
            {ranked_where_sql}
            ORDER BY placement
            LIMIT ?
            """,
            [*params, *ranked_params, int(limit)],
        ).fetchdf()

        location_rows = con.execute(
            f"""
            SELECT
                location,
                COUNT(*) AS count,
                MIN(total_time_min) AS fastest_time_min
            FROM race_results
            WHERE {where_sql}
            GROUP BY location
            ORDER BY lower(location)
            """,
            params,
        ).fetchdf()

        placement_lookup = None
        if target_time_min is not None and total_rows > 0:
            less_count = con.execute(
                f"SELECT COUNT(*) FROM race_results WHERE {where_sql} AND total_time_min < ?",
                [*params, float(target_time_min)],
            ).fetchone()[0]
            equal_count = con.execute(
                f"SELECT COUNT(*) FROM race_results WHERE {where_sql} AND total_time_min = ?",
                [*params, float(target_time_min)],
            ).fetchone()[0]
            placement_lookup = {
                "target_time_min": float(target_time_min),
                "placement": int(less_count) + 1,
                "out_of": int(total_rows),
                "exact_matches": int(equal_count),
            }

        return {
            "filters": {
                "season": int(season),
                "division": normalized_division,
                "gender": normalized_gender,
                "age_group": normalized_age_group,
                "athlete_name": normalized_athlete_name,
            },
            "count": int(total_rows),
            "limit": int(limit),
            "rows": df_to_records(ranking_rows),
            "locations": df_to_records(location_rows),
            "total_locations": int(len(location_rows)),
            "placement_lookup": placement_lookup,
        }

    def athlete_profile_by_id(self, *, athlete_id: str, division: Optional[str] = None) -> dict:
        """Return an Athlete Profile by stable athlete identifier."""
        athlete_id_trimmed = athlete_id.strip()
        if not athlete_id_trimmed:
            raise ReportingQueryError("athlete_id is required.")
        return self._build_athlete_profile_payload(athlete_id_trimmed, division)

    def athlete_profile_by_name(self, *, name: str, division: Optional[str] = None) -> dict:
        """Return an Athlete Profile by exact name when it resolves uniquely.

        Ambiguous names raise ``ReportingConflictError`` so callers can retry
        with an athlete id from the athlete-search flow.
        """
        name_trimmed = name.strip()
        if not name_trimmed:
            raise ReportingQueryError("name is required.")
        con = self.connection()
        athlete_id_rows = con.execute(
            """
            SELECT DISTINCT ar.athlete_id
            FROM race_results rr
            JOIN athlete_results ar ON ar.result_id = rr.result_id
            WHERE lower(rr.name) = lower(?)
            """,
            [name_trimmed],
        ).fetchall()
        athlete_ids = sorted(
            {
                str(row[0]).strip()
                for row in athlete_id_rows
                if row and row[0] is not None and str(row[0]).strip()
            },
            key=str.casefold,
        )

        if not athlete_ids:
            raise ReportingNotFoundError(f"No races found for '{name_trimmed}'.")
        if len(athlete_ids) > 1:
            raise ReportingConflictError(
                "Multiple athlete_ids match this name. "
                "Resolve athlete_id from /api/athletes/search and retry."
            )
        return self._build_athlete_profile_payload(athlete_ids[0], division)

    def _build_athlete_profile_payload(
        self,
        athlete_id: str,
        division: Optional[str] = None,
    ) -> dict:
        """Build the Athlete Profile payload for one athlete id.

        The profile combines identity fields, summary stats, personal bests,
        average Segment times, season progression, and per-race progression
        metrics. A Division filter narrows the race set; when no Division filter
        is provided and the athlete has multiple Divisions, the profile-level
        Division is intentionally omitted to avoid implying comparability.
        """
        con = self.connection()
        division_filter = _normalize_profile_division_filter(division)
        available_divisions = _load_profile_divisions_for_athlete_id(con, athlete_id)
        df = _load_profile_rows_for_athlete_id(con, athlete_id, division_filter)
        if df.empty:
            if division_filter is not None:
                raise ReportingNotFoundError(
                    f"No races found for athlete_id '{athlete_id}' in division '{division_filter}'."
                )
            raise ReportingNotFoundError(f"No races found for athlete_id '{athlete_id}'.")

        recent = df.iloc[0]

        def row_text(column: str) -> Optional[str]:
            """Return normalized text from the most recent profile row."""
            value = recent.get(column)
            if value is None or not pd.notna(value):
                return None
            return normalize_optional_text(str(value))

        nationality = None
        if "athlete_index_nationality" in df.columns and df["athlete_index_nationality"].notna().any():
            nationality = normalize_optional_text(str(df["athlete_index_nationality"].dropna().iloc[0]))

        valid_times = (
            pd.to_numeric(df["total_time_min"], errors="coerce").dropna()
            if "total_time_min" in df.columns
            else pd.Series(dtype=float)
        )
        best_ag = (
            pd.to_numeric(df["age_group_rank"], errors="coerce").dropna()
            if "age_group_rank" in df.columns
            else pd.Series(dtype=float)
        )
        years = (
            pd.to_numeric(df["year"], errors="coerce").dropna()
            if "year" in df.columns
            else pd.Series(dtype=float)
        )

        personal_bests: dict = {}
        average_times: dict = {}
        metric_series = _build_profile_metric_series(df)
        race_columns = _load_race_results_columns(con)
        for metric_key, series in metric_series.items():
            valid = pd.to_numeric(series, errors="coerce")
            valid = valid[valid > 0].dropna()
            if valid.empty:
                continue

            average_times[metric_key] = {"time": float(valid.mean())}
            average_percentiles: list[float] = []
            for value_idx, value in valid.items():
                percentile = _compute_profile_metric_percentile(
                    con,
                    cohort_row=df.loc[value_idx],
                    metric_key=metric_key,
                    metric_time=float(value),
                    race_columns=race_columns,
                )
                if percentile is not None:
                    average_percentiles.append(percentile)
            if average_percentiles:
                average_times[metric_key]["percentile"] = float(np.mean(average_percentiles))

            idx = valid.idxmin()
            pb_row = df.loc[idx]
            pb_year = pb_row.get("year")
            pb_location = pb_row.get("location")
            personal_best = {
                "time": float(valid[idx]),
                "result_id": pb_row["result_id"],
                "location": (
                    normalize_optional_text(str(pb_location))
                    if pb_location is not None and pd.notna(pb_location)
                    else None
                ),
                "year": int(pb_year) if pb_year is not None and pd.notna(pb_year) else None,
            }
            percentile = _compute_profile_metric_percentile(
                con,
                cohort_row=pb_row,
                metric_key=metric_key,
                metric_time=personal_best["time"],
                race_columns=race_columns,
            )
            if percentile is not None:
                personal_best["percentile"] = percentile
            personal_bests[metric_key] = personal_best

        seasons = []
        if "year" in df.columns and "total_time_min" in df.columns:
            for year_val, group in df.groupby("year", sort=True):
                year_times = pd.to_numeric(group["total_time_min"], errors="coerce").dropna()
                if year_times.empty or not pd.notna(year_val):
                    continue
                seasons.append(
                    {
                        "season": str(int(year_val)),
                        "best_time": float(year_times.min()),
                        "race_count": int(len(group)),
                    }
                )

        races = []
        for _, race_row in df.iterrows():
            ag_rank = race_row.get("age_group_rank")
            total_time = race_row.get("total_time_min")
            race_year = race_row.get("year")
            race_location = race_row.get("location")
            race_start_date = race_row.get("start_date")
            normalized_start_date = str(race_start_date) if race_start_date is not None and pd.notna(race_start_date) else None
            progression_metrics: dict[str, Optional[float]] = {}
            for column in _PROFILE_RACE_PROGRESS_COLUMNS:
                value = race_row.get(column)
                progression_metrics[column] = float(value) if value is not None and pd.notna(value) else None
            run_total = progression_metrics.get("run_time_min")
            roxzone = progression_metrics.get("roxzone_time_min")
            progression_metrics["runplusroxzone_time_min"] = (
                float(run_total + roxzone) if run_total is not None and roxzone is not None else None
            )
            races.append(
                {
                    "result_id": race_row["result_id"],
                    "location": (
                        normalize_optional_text(str(race_location))
                        if race_location is not None and pd.notna(race_location)
                        else None
                    ),
                    "year": int(race_year) if race_year is not None and pd.notna(race_year) else None,
                    "total_time": float(total_time) if total_time is not None and pd.notna(total_time) else None,
                    "age_group_rank": int(ag_rank) if ag_rank is not None and pd.notna(ag_rank) else None,
                    "start_date": normalized_start_date,
                    **progression_metrics,
                }
            )

        profile_name = row_text("name") or row_text("athlete_name") or "Athlete"
        profile_gender = row_text("gender") or row_text("athlete_index_gender")
        profile_division = row_text("division")
        if division_filter is None and len(available_divisions) > 1:
            profile_division = None

        return {
            "athlete": {
                "athlete_id": athlete_id,
                "name": profile_name,
                "gender": profile_gender,
                "division": profile_division,
                "age_group": row_text("age_group"),
                "nationality": nationality,
            },
            "filters": {"division": division_filter},
            "available_divisions": available_divisions,
            "summary": {
                "total_races": int(len(df)),
                "best_overall_time": float(valid_times.min()) if not valid_times.empty else None,
                "best_age_group_finish": int(best_ag.min()) if not best_ag.empty else None,
                "first_season": str(int(years.min())) if not years.empty else None,
            },
            "personal_bests": personal_bests,
            "average_times": average_times,
            "seasons": seasons,
            "races": races,
        }


def _gender_filter(gender: str) -> tuple[list[str], list[object]]:
    """Return SQL clauses and parameters for a gender filter.

    The reporting database has historically contained both abbreviated and full
    gender values. This helper keeps that equivalence in one place for query
    paths that still build SQL directly.
    """
    gender_clauses = []
    gender_params: list[object] = []
    normalized_gender_key = gender.casefold()
    if normalized_gender_key in {"m", "male"}:
        gender_clauses.append("lower(gender) IN (?, ?)")
        gender_params.extend(["m", "male"])
    elif normalized_gender_key in {"f", "female"}:
        gender_clauses.append("lower(gender) IN (?, ?)")
        gender_params.extend(["f", "female"])
    else:
        gender_clauses.append("lower(gender) = ?")
        gender_params.append(normalized_gender_key)
    return gender_clauses, gender_params


def _load_profile_divisions_for_athlete_id(con, athlete_id: str) -> list[str]:
    """Return the sorted Divisions in which an athlete has Results."""
    rows = con.execute(
        """
        SELECT DISTINCT trim(CAST(rr.division AS VARCHAR)) AS division
        FROM athlete_results ar
        JOIN race_results rr ON rr.result_id = ar.result_id
        WHERE ar.athlete_id = ?
          AND rr.division IS NOT NULL
          AND trim(CAST(rr.division AS VARCHAR)) <> ''
        ORDER BY lower(trim(CAST(rr.division AS VARCHAR))), trim(CAST(rr.division AS VARCHAR))
        """,
        [athlete_id],
    ).fetchall()
    return [str(row[0]) for row in rows if row and row[0] is not None and str(row[0]).strip()]


def _load_profile_rows_for_athlete_id(
    con,
    athlete_id: str,
    division: Optional[str] = None,
) -> pd.DataFrame:
    """Load all Race rows needed to build an Athlete Profile.

    Args:
        con: DuckDB connection.
        athlete_id: Stable athlete identifier from ``athlete_results``.
        division: Optional Division filter.

    Returns:
        A DataFrame containing race rows, athlete identity fields, and an
        ``age_group_rank`` column. When the fixture/artifact lacks the columns
        needed to recompute age-group rank, the rank column is present but null.
    """
    race_columns = _load_race_results_columns(con)
    can_compute_ag_rank_fallback = {
        "season",
        "location",
        "division",
        "gender",
        "age_group",
        "total_time_min",
    }.issubset(race_columns)
    normalized_division = _normalize_profile_division_filter(division)
    division_clause = ""
    params: list[object] = [athlete_id]
    if normalized_division is not None:
        division_clause = " AND lower(rr.division) = ?"
        params.append(normalized_division.casefold())

    if can_compute_ag_rank_fallback:
        sql = f"""
            WITH athlete_rows AS (
                SELECT
                    rr.*,
                    ar.athlete_id,
                    COALESCE(NULLIF(rr.name, ''), ai.canonical_name) AS athlete_name,
                    ai.canonical_name AS athlete_canonical_name,
                    ai.gender AS athlete_index_gender,
                    ai.nationality AS athlete_index_nationality
                FROM athlete_results ar
                JOIN race_results rr ON rr.result_id = ar.result_id
                LEFT JOIN athlete_index ai ON ai.athlete_id = ar.athlete_id
                WHERE ar.athlete_id = ?
                {division_clause}
            ),
            cohort_keys AS (
                SELECT DISTINCT season, location, division, gender, age_group
                FROM athlete_rows
            ),
            ag_rankings AS (
                SELECT
                    rr.result_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY rr.season, rr.location, rr.division, rr.gender, rr.age_group
                        ORDER BY rr.total_time_min
                    ) AS age_group_rank
                FROM race_results rr
                JOIN cohort_keys ck
                    ON rr.season IS NOT DISTINCT FROM ck.season
                   AND rr.location IS NOT DISTINCT FROM ck.location
                   AND rr.division IS NOT DISTINCT FROM ck.division
                   AND rr.gender IS NOT DISTINCT FROM ck.gender
                   AND rr.age_group IS NOT DISTINCT FROM ck.age_group
                WHERE rr.total_time_min IS NOT NULL
            )
            SELECT athlete_rows.*, ag_rankings.age_group_rank
            FROM athlete_rows
            LEFT JOIN ag_rankings ON ag_rankings.result_id = athlete_rows.result_id
            ORDER BY athlete_rows.year DESC NULLS LAST, athlete_rows.location ASC NULLS LAST, athlete_rows.result_id ASC
        """
    else:
        sql = f"""
            SELECT
                rr.*,
                ar.athlete_id,
                COALESCE(NULLIF(rr.name, ''), ai.canonical_name) AS athlete_name,
                ai.canonical_name AS athlete_canonical_name,
                ai.gender AS athlete_index_gender,
                ai.nationality AS athlete_index_nationality,
                CAST(NULL AS INTEGER) AS age_group_rank
            FROM athlete_results ar
            JOIN race_results rr ON rr.result_id = ar.result_id
            LEFT JOIN athlete_index ai ON ai.athlete_id = ar.athlete_id
            WHERE ar.athlete_id = ?
            {division_clause}
            ORDER BY rr.year DESC NULLS LAST, rr.location ASC NULLS LAST, rr.result_id ASC
        """

    return con.execute(sql, params).fetchdf()


def _build_profile_metric_series(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Return profile metric series keyed by frontend metric name.

    Station and overall metrics map directly to stored time columns. The
    ``runplusroxzone`` metric is derived only when both required source columns
    are present and positive.
    """
    metrics: dict[str, pd.Series] = {}
    for metric_key, column_name in _PROFILE_TIME_COLUMN_MAP.items():
        if column_name in df.columns:
            metrics[metric_key] = pd.to_numeric(df[column_name], errors="coerce")

    if {"run_time_min", "roxzone_time_min"}.issubset(df.columns):
        run_values = pd.to_numeric(df["run_time_min"], errors="coerce")
        roxzone_values = pd.to_numeric(df["roxzone_time_min"], errors="coerce")
        combined = run_values + roxzone_values
        metrics[_PROFILE_RUN_ROXZONE_KEY] = combined.where((run_values > 0) & (roxzone_values > 0))

    return metrics


def _resolve_profile_metric_sql(
    metric_key: str,
    race_columns: set[str],
) -> Optional[tuple[str, str]]:
    """Resolve a profile metric to SQL expression and validity predicate."""
    if metric_key == _PROFILE_RUN_ROXZONE_KEY:
        required = {"run_time_min", "roxzone_time_min"}
        if not required.issubset(race_columns):
            return None
        return (
            "(rr.run_time_min + rr.roxzone_time_min)",
            (
                "rr.run_time_min IS NOT NULL AND rr.roxzone_time_min IS NOT NULL "
                "AND rr.run_time_min > 0 AND rr.roxzone_time_min > 0"
            ),
        )

    column_name = _PROFILE_TIME_COLUMN_MAP.get(metric_key)
    if column_name is None or column_name not in race_columns:
        return None
    return (f"rr.{column_name}", f"rr.{column_name} IS NOT NULL AND rr.{column_name} > 0")


def _compute_profile_metric_percentile(
    con,
    *,
    cohort_row: pd.Series,
    metric_key: str,
    metric_time: float,
    race_columns: set[str],
) -> Optional[float]:
    """Compute a historical Division/gender percentile for one profile metric.

    Returns ``None`` when the metric value is invalid, the database artifact
    lacks required columns, or the percentile query fails. The caller treats a
    missing percentile as absent optional enrichment rather than a hard profile
    failure.
    """
    try:
        metric_value = float(metric_time)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(metric_value) or metric_value <= 0:
        return None

    if not _PROFILE_PERCENTILE_COHORT_COLUMNS.issubset(race_columns):
        return None
    metric_sql = _resolve_profile_metric_sql(metric_key, race_columns)
    if metric_sql is None:
        return None
    metric_expr, metric_predicate = metric_sql

    try:
        row = con.execute(
            f"""
            SELECT
                COUNT(*) AS cohort_size,
                SUM(CASE WHEN {metric_expr} < ? THEN 1 ELSE 0 END) AS less_count
            FROM race_results rr
            WHERE rr.division IS NOT DISTINCT FROM ?
              AND rr.gender IS NOT DISTINCT FROM ?
              AND {metric_predicate}
            """,
            [metric_value, cohort_row.get("division"), cohort_row.get("gender")],
        ).fetchone()
    except Exception:
        logger.warning(
            "profile percentile computation skipped metric=%s result_id=%s",
            metric_key,
            cohort_row.get("result_id"),
            exc_info=True,
        )
        return None

    if row is None:
        return None
    cohort_size = int(row[0] or 0)
    if cohort_size <= 0:
        return None
    if cohort_size == 1:
        return 1.0

    less_count = int(row[1] or 0)
    percentile = 1.0 - less_count / (cohort_size - 1)
    return float(max(0.0, min(1.0, percentile)))
