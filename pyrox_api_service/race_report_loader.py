"""Bounded DuckDB loading for the REST/MCP race report response."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd


HISTOGRAM_BINS = 22


@dataclass(frozen=True)
class RaceReportLoadRequest:
    """Data requirements for one bounded race report response."""

    result_id: str
    cohort_time_window_min: Optional[float]
    selected_split: Optional[str]
    cohort_preview_limit: Optional[int]
    cohort_splits_preview_limit: Optional[int]


@dataclass(frozen=True)
class DistributionData:
    """Summary and histogram calculated without materializing source rows."""

    stats: Optional[dict[str, Any]]
    histogram: Optional[dict[str, Any]]


@dataclass(frozen=True)
class PreviewData:
    """A bounded row preview plus the full matching cardinality."""

    columns: list[str]
    rows: list[dict[str, Any]]
    total: int


@dataclass(frozen=True)
class BoundedRaceReport:
    """All data needed to shape the REST/MCP race report payload."""

    race: dict[str, Any]
    splits: list[dict[str, Any]]
    cohort: DistributionData
    time_window: Optional[DistributionData]
    selected_split_cohort: Optional[DistributionData]
    selected_split_time_window: Optional[DistributionData]
    cohort_preview: Optional[PreviewData]
    cohort_splits_preview: Optional[PreviewData]
    time_window_splits_preview: Optional[PreviewData]


@dataclass(frozen=True)
class _SelectedRace:
    record: dict[str, Any]
    location: object
    season: Optional[int]
    total_time_min: Optional[float]


@dataclass(frozen=True)
class _FetchedSplits:
    records: list[dict[str, Any]]
    athlete_times: dict[str, float]


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def _fetch_race(con, result_id: str) -> _SelectedRace:
    frame = con.execute(
        """
        WITH picked AS (
            SELECT season, location, division, gender, age_group
            FROM race_results
            WHERE result_id = ?
        ),
        event_rankings AS (
            SELECT
                r.result_id,
                ROW_NUMBER() OVER (
                    PARTITION BY r.season, r.location, r.division, r.gender, r.age_group
                    ORDER BY r.total_time_min
                ) AS event_rank,
                COUNT(*) OVER (
                    PARTITION BY r.season, r.location, r.division, r.gender, r.age_group
                ) AS event_size,
                1.0 - PERCENT_RANK() OVER (
                    PARTITION BY r.season, r.location, r.division, r.gender, r.age_group
                    ORDER BY r.total_time_min
                ) AS event_percentile
            FROM race_results r
            JOIN picked p
              ON r.season IS NOT DISTINCT FROM p.season
             AND r.location IS NOT DISTINCT FROM p.location
             AND r.division IS NOT DISTINCT FROM p.division
             AND r.gender IS NOT DISTINCT FROM p.gender
             AND r.age_group IS NOT DISTINCT FROM p.age_group
            WHERE r.total_time_min IS NOT NULL
        )
        SELECT
            r.*,
            er.event_rank,
            er.event_size,
            er.event_percentile,
            rr.season_rank,
            rr.season_size,
            rr.season_percentile,
            rr.overall_rank,
            rr.overall_size,
            rr.overall_percentile
        FROM race_results r
        LEFT JOIN event_rankings er ON er.result_id = r.result_id
        LEFT JOIN race_rankings rr ON rr.result_id = r.result_id
        WHERE r.result_id = ?
        """,
        [result_id, result_id],
    ).fetchdf()
    rows = _records(frame)
    if not rows:
        raise ValueError(f"result_id not found: {result_id}")
    raw = frame.iloc[0]
    season = raw.get("season")
    total_time = raw.get("total_time_min")
    return _SelectedRace(
        record=rows[0],
        location=raw.get("location"),
        season=None if season is None or pd.isna(season) else int(season),
        total_time_min=(
            None if total_time is None or pd.isna(total_time) else float(total_time)
        ),
    )


def _distribution(
    con,
    values_sql: str,
    params: list[object],
    *,
    athlete_value: Optional[float],
    min_value: Optional[float] = None,
) -> DistributionData:
    athlete = athlete_value
    if athlete is not None:
        athlete = float(athlete)
    if min_value is not None and athlete is not None and athlete < min_value:
        athlete = None

    minimum_clause = "AND value >= ?" if min_value is not None else ""
    query_params = [*params]
    if min_value is not None:
        query_params.append(float(min_value))
    query_params.extend([athlete, HISTOGRAM_BINS, HISTOGRAM_BINS - 1])

    frame = con.execute(
        f"""
        WITH raw_values AS (
            {values_sql}
        ),
        values AS (
            SELECT CAST(value AS DOUBLE) AS value
            FROM raw_values
            WHERE value IS NOT NULL {minimum_clause}
        ),
        stats AS (
            SELECT
                COUNT(*) AS value_count,
                MIN(value) AS min_value,
                MAX(value) AS max_value,
                AVG(value) AS mean_value,
                MEDIAN(value) AS median_value,
                QUANTILE_CONT(value, 0.1) AS p10_value,
                QUANTILE_CONT(value, 0.9) AS p90_value,
                COUNT(*) FILTER (WHERE value < ?) AS lower_count
            FROM values
        ),
        bucketed AS (
            SELECT
                CASE
                    WHEN stats.max_value = stats.min_value THEN 0
                    ELSE LEAST(
                        CAST(FLOOR(
                            ((values.value - stats.min_value)
                             / (stats.max_value - stats.min_value)) * ?
                        ) AS INTEGER),
                        ?
                    )
                END AS bucket_index
            FROM values
            CROSS JOIN stats
        ),
        bucket_counts AS (
            SELECT bucket_index, COUNT(*) AS bucket_count
            FROM bucketed
            GROUP BY bucket_index
        )
        SELECT stats.*, bucket_counts.bucket_index, bucket_counts.bucket_count
        FROM stats
        LEFT JOIN bucket_counts ON TRUE
        ORDER BY bucket_counts.bucket_index
        """,
        query_params,
    ).fetchdf()

    if frame.empty or int(frame.iloc[0]["value_count"]) == 0:
        return DistributionData(stats=None, histogram=None)

    first = frame.iloc[0]
    count = int(first["value_count"])
    min_value_result = float(first["min_value"])
    raw_max = float(first["max_value"])
    histogram_max = raw_max if raw_max != min_value_result else min_value_result + 1.0
    counts = [0] * HISTOGRAM_BINS
    for _, row in frame.iterrows():
        bucket_index = row["bucket_index"]
        if bucket_index is None or pd.isna(bucket_index):
            continue
        counts[int(bucket_index)] = int(row["bucket_count"])

    edges = np.linspace(min_value_result, histogram_max, HISTOGRAM_BINS + 1)
    histogram = {
        "bins": [
            {
                "start": float(edges[index]),
                "end": float(edges[index + 1]),
                "count": counts[index],
            }
            for index in range(HISTOGRAM_BINS)
        ],
        "min": min_value_result,
        "max": histogram_max,
        "count": count,
        "athlete_value": athlete,
        "athlete_percentile": (
            None
            if athlete is None
            else 1.0
            if count == 1
            else 1.0 - int(first["lower_count"]) / (count - 1)
        ),
    }
    stats = {
        "count": count,
        "min": min_value_result,
        "max": raw_max,
        "mean": float(first["mean_value"]),
        "median": float(first["median_value"]),
        "p10": float(first["p10_value"]),
        "p90": float(first["p90_value"]),
    }
    return DistributionData(stats=stats, histogram=histogram)


def _cohort_distribution(
    con,
    result_id: str,
    athlete_value: Optional[float],
) -> DistributionData:
    return _distribution(
        con,
        """
        WITH picked AS (
            SELECT season, location, division, gender, age_group
            FROM race_results
            WHERE result_id = ?
        )
        SELECT r.total_time_min AS value
        FROM race_results r
        JOIN picked p
          ON r.season IS NOT DISTINCT FROM p.season
         AND r.location IS NOT DISTINCT FROM p.location
         AND r.division IS NOT DISTINCT FROM p.division
         AND r.gender IS NOT DISTINCT FROM p.gender
         AND r.age_group IS NOT DISTINCT FROM p.age_group
        """,
        [result_id],
        athlete_value=athlete_value,
    )


def _time_window_distribution(
    con,
    *,
    location: object,
    season: int,
    lower_bound: float,
    upper_bound: float,
    athlete_value: float,
) -> DistributionData:
    return _distribution(
        con,
        """
        SELECT total_time_min AS value
        FROM race_results
        WHERE location IS NOT DISTINCT FROM ?
          AND season IS NOT DISTINCT FROM ?
          AND total_time_min IS NOT NULL
          AND total_time_min BETWEEN ? AND ?
        """,
        [location, season, lower_bound, upper_bound],
        athlete_value=athlete_value,
    )


def _fetch_splits(
    con,
    *,
    result_id: str,
    location: object,
    season: int,
    lower_bound: Optional[float],
    upper_bound: Optional[float],
) -> _FetchedSplits:
    if lower_bound is None or upper_bound is None:
        frame = con.execute(
            """
            SELECT split_name, split_time_min, split_rank, split_size, split_percentile
            FROM split_percentiles
            WHERE result_id = ?
            ORDER BY split_name
            """,
            [result_id],
        ).fetchdf()
        return _fetched_splits(frame)

    frame = con.execute(
        """
        WITH time_window_results AS (
            SELECT result_id
            FROM race_results
            WHERE location IS NOT DISTINCT FROM ?
              AND season IS NOT DISTINCT FROM ?
              AND total_time_min IS NOT NULL
              AND total_time_min BETWEEN ? AND ?
        ),
        athlete_splits AS (
            SELECT split_name, split_time_min, split_rank, split_size, split_percentile
            FROM split_percentiles
            WHERE result_id = ?
        ),
        window_stats AS (
            SELECT
                athlete.split_name,
                athlete.split_time_min,
                COUNT(cohort.split_time_min) AS cohort_size,
                COUNT(cohort.split_time_min) FILTER (
                    WHERE cohort.split_time_min < athlete.split_time_min
                ) AS lower_count
            FROM athlete_splits athlete
            LEFT JOIN time_window_results window_result ON TRUE
            LEFT JOIN split_percentiles cohort
              ON cohort.result_id = window_result.result_id
             AND cohort.split_name = athlete.split_name
            GROUP BY athlete.split_name, athlete.split_time_min
        )
        SELECT
            athlete.split_name,
            athlete.split_time_min,
            athlete.split_rank,
            athlete.split_size,
            athlete.split_percentile,
            CASE
                WHEN athlete.split_time_min IS NULL OR stats.cohort_size = 0 THEN NULL
                WHEN stats.cohort_size = 1 THEN 1.0
                ELSE 1.0 - CAST(stats.lower_count AS DOUBLE) / (stats.cohort_size - 1)
            END AS split_percentile_time_window
        FROM athlete_splits athlete
        LEFT JOIN window_stats stats
          ON stats.split_name = athlete.split_name
         AND stats.split_time_min IS NOT DISTINCT FROM athlete.split_time_min
        ORDER BY athlete.split_name
        """,
        [location, season, lower_bound, upper_bound, result_id],
    ).fetchdf()
    return _fetched_splits(frame)


def _fetched_splits(frame: pd.DataFrame) -> _FetchedSplits:
    athlete_times: dict[str, float] = {}
    if not frame.empty:
        for _, row in frame.iterrows():
            name = row.get("split_name")
            value = row.get("split_time_min")
            if name is None or value is None or pd.isna(value):
                continue
            athlete_times[str(name).casefold()] = float(value)
    return _FetchedSplits(records=_records(frame), athlete_times=athlete_times)


def _selected_split_distribution(
    con,
    *,
    result_id: str,
    split_name: str,
    athlete_value: Optional[float],
    min_value: Optional[float],
    time_window: Optional[tuple[object, int, float, float]],
) -> DistributionData:
    if time_window is None:
        values_sql = """
            WITH picked AS (
                SELECT season, location, division, gender, age_group
                FROM race_results
                WHERE result_id = ?
            )
            SELECT sp.split_time_min AS value
            FROM split_percentiles sp
            JOIN picked p
              ON sp.season IS NOT DISTINCT FROM p.season
             AND sp.location IS NOT DISTINCT FROM p.location
             AND sp.division IS NOT DISTINCT FROM p.division
             AND sp.gender IS NOT DISTINCT FROM p.gender
             AND sp.age_group IS NOT DISTINCT FROM p.age_group
            WHERE lower(sp.split_name) = lower(?)
        """
        params: list[object] = [result_id, split_name]
    else:
        location, season, lower_bound, upper_bound = time_window
        values_sql = """
            WITH time_window_results AS (
                SELECT result_id
                FROM race_results
                WHERE location IS NOT DISTINCT FROM ?
                  AND season IS NOT DISTINCT FROM ?
                  AND total_time_min IS NOT NULL
                  AND total_time_min BETWEEN ? AND ?
            )
            SELECT sp.split_time_min AS value
            FROM split_percentiles sp
            JOIN time_window_results window_result
              ON sp.result_id = window_result.result_id
            WHERE lower(sp.split_name) = lower(?)
        """
        params = [location, season, lower_bound, upper_bound, split_name]
    return _distribution(
        con,
        values_sql,
        params,
        athlete_value=athlete_value,
        min_value=min_value,
    )


def _preview(frame: pd.DataFrame) -> PreviewData:
    columns = [column for column in frame.columns if column != "__total"]
    if frame.empty:
        return PreviewData(columns=columns, rows=[], total=0)
    total = int(frame.iloc[0]["__total"])
    bounded = frame.drop(columns=["__total"])
    return PreviewData(columns=columns, rows=_records(bounded), total=total)


def _cohort_preview(con, result_id: str, limit: int) -> PreviewData:
    frame = con.execute(
        """
        WITH picked AS (
            SELECT season, location, division, gender, age_group
            FROM race_results
            WHERE result_id = ?
        ),
        cohort_rows AS (
            SELECT r.*
            FROM race_results r
            JOIN picked p
              ON r.season IS NOT DISTINCT FROM p.season
             AND r.location IS NOT DISTINCT FROM p.location
             AND r.division IS NOT DISTINCT FROM p.division
             AND r.gender IS NOT DISTINCT FROM p.gender
             AND r.age_group IS NOT DISTINCT FROM p.age_group
        ),
        event_rankings AS (
            SELECT
                c.result_id,
                ROW_NUMBER() OVER (
                    PARTITION BY c.season, c.location, c.division, c.gender, c.age_group
                    ORDER BY c.total_time_min
                ) AS event_rank,
                COUNT(*) OVER (
                    PARTITION BY c.season, c.location, c.division, c.gender, c.age_group
                ) AS event_size,
                1.0 - PERCENT_RANK() OVER (
                    PARTITION BY c.season, c.location, c.division, c.gender, c.age_group
                    ORDER BY c.total_time_min
                ) AS event_percentile
            FROM cohort_rows c
            WHERE c.total_time_min IS NOT NULL
        )
        SELECT
            c.*,
            er.event_rank,
            er.event_size,
            er.event_percentile,
            COUNT(*) OVER () AS __total
        FROM cohort_rows c
        LEFT JOIN event_rankings er ON er.result_id = c.result_id
        ORDER BY c.total_time_min, c.result_id
        LIMIT ?
        """,
        [result_id, limit],
    ).fetchdf()
    return _preview(frame)


def _cohort_splits_preview(con, result_id: str, limit: int) -> PreviewData:
    frame = con.execute(
        """
        WITH picked AS (
            SELECT season, location, division, gender, age_group
            FROM race_results
            WHERE result_id = ?
        )
        SELECT sp.*, COUNT(*) OVER () AS __total
        FROM split_percentiles sp
        JOIN picked p
          ON sp.season IS NOT DISTINCT FROM p.season
         AND sp.location IS NOT DISTINCT FROM p.location
         AND sp.division IS NOT DISTINCT FROM p.division
         AND sp.gender IS NOT DISTINCT FROM p.gender
         AND sp.age_group IS NOT DISTINCT FROM p.age_group
        ORDER BY sp.split_name, sp.split_time_min, sp.result_id
        LIMIT ?
        """,
        [result_id, limit],
    ).fetchdf()
    return _preview(frame)


def _time_window_splits_preview(
    con,
    *,
    location: object,
    season: int,
    lower_bound: float,
    upper_bound: float,
    limit: int,
) -> PreviewData:
    frame = con.execute(
        """
        WITH time_window_results AS (
            SELECT result_id
            FROM race_results
            WHERE location IS NOT DISTINCT FROM ?
              AND season IS NOT DISTINCT FROM ?
              AND total_time_min IS NOT NULL
              AND total_time_min BETWEEN ? AND ?
        )
        SELECT sp.*, COUNT(*) OVER () AS __total
        FROM split_percentiles sp
        JOIN time_window_results window_result
          ON sp.result_id = window_result.result_id
        ORDER BY sp.split_name, sp.split_time_min, sp.result_id
        LIMIT ?
        """,
        [location, season, lower_bound, upper_bound, limit],
    ).fetchdf()
    return _preview(frame)


def load_bounded_race_report(con, request: RaceReportLoadRequest) -> BoundedRaceReport:
    """Load one report without materializing unrequested cohort rows."""
    selected_race = _fetch_race(con, request.result_id)
    race = selected_race.record
    athlete_total = selected_race.total_time_min
    location = selected_race.location
    season_value = selected_race.season
    season = season_value if season_value is not None else 0

    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    time_window: Optional[tuple[object, int, float, float]] = None
    if request.cohort_time_window_min is not None:
        if athlete_total is None:
            raise ValueError(f"No total_time_min data for result_id: {request.result_id}")
        if season_value is None:
            raise ValueError("season is required to build the time-window cohort.")
        lower_bound = athlete_total - request.cohort_time_window_min
        upper_bound = athlete_total + request.cohort_time_window_min
        time_window = (location, season, lower_bound, upper_bound)

    fetched_splits = _fetch_splits(
        con,
        result_id=request.result_id,
        location=location,
        season=season,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )
    cohort = _cohort_distribution(con, request.result_id, athlete_total)
    window_distribution = None
    if time_window is not None:
        window_distribution = _time_window_distribution(
            con,
            location=location,
            season=season,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            athlete_value=athlete_total,
        )

    selected_cohort = None
    selected_window = None
    if request.selected_split is not None:
        athlete_split = fetched_splits.athlete_times.get(
            request.selected_split.casefold()
        )
        minimum = 1.0 if request.selected_split.casefold().startswith("run") else None
        selected_cohort = _selected_split_distribution(
            con,
            result_id=request.result_id,
            split_name=request.selected_split,
            athlete_value=athlete_split,
            min_value=minimum,
            time_window=None,
        )
        if time_window is not None:
            selected_window = _selected_split_distribution(
                con,
                result_id=request.result_id,
                split_name=request.selected_split,
                athlete_value=athlete_split,
                min_value=minimum,
                time_window=time_window,
            )

    cohort_preview = None
    if request.cohort_preview_limit is not None:
        cohort_preview = _cohort_preview(con, request.result_id, request.cohort_preview_limit)

    cohort_splits_preview = None
    time_window_splits_preview = None
    if request.cohort_splits_preview_limit is not None:
        cohort_splits_preview = _cohort_splits_preview(
            con,
            request.result_id,
            request.cohort_splits_preview_limit,
        )
        if time_window is not None:
            time_window_splits_preview = _time_window_splits_preview(
                con,
                location=location,
                season=season,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                limit=request.cohort_splits_preview_limit,
            )

    return BoundedRaceReport(
        race=race,
        splits=fetched_splits.records,
        cohort=cohort,
        time_window=window_distribution,
        selected_split_cohort=selected_cohort,
        selected_split_time_window=selected_window,
        cohort_preview=cohort_preview,
        cohort_splits_preview=cohort_splits_preview,
        time_window_splits_preview=time_window_splits_preview,
    )
