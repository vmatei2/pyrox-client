"""
Reporting helpers for PyroxClient with DuckDB integration.
"""

from __future__ import annotations

import re
import logging
import time
from typing import Iterable, Optional, Tuple

import duckdb
import pandas as pd
import numpy as np

from .core import PyroxClient
from .errors import AthleteNotFound

logger = logging.getLogger("pyrox.reporting")


def _normalize_metric_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


_TIME_COLUMNS = (
    "roxzone_time_min",
    "run1_time_min",
    "run2_time_min",
    "run3_time_min",
    "run4_time_min",
    "run5_time_min",
    "run6_time_min",
    "run7_time_min",
    "run8_time_min",
    "run_time_min",
    "total_time_min",
    "skiErg_time_min",
    "sledPush_time_min",
    "sledPull_time_min",
    "burpeeBroadJump_time_min",
    "rowErg_time_min",
    "farmersCarry_time_min",
    "sandbagLunges_time_min",
    "wallBalls_time_min",
    "work_time_min",
)


def _build_time_column_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}

    def add(alias: str, column: str) -> None:
        aliases[_normalize_metric_name(alias)] = column

    for column in _TIME_COLUMNS:
        add(column, column)
        if column.endswith("_time_min"):
            add(column[:-9], column)
            add(column.replace("_time_min", "_time"), column)

    add("run_total", "run_time_min")
    add("work_total", "work_time_min")
    add("total", "total_time_min")
    add("total_time", "total_time_min")

    return aliases


_TIME_COLUMN_ALIASES = _build_time_column_aliases()


def _resolve_time_column(metric: str) -> str:
    if metric is None or str(metric).strip() == "":
        raise ValueError("metric must be a non-empty string.")
    normalized = _normalize_metric_name(str(metric))
    column = _TIME_COLUMN_ALIASES.get(normalized)
    if column is None:
        examples = ", ".join(sorted(set(_TIME_COLUMNS))[:6])
        raise ValueError(
            "Unknown metric. Provide a known split or time column name, "
            f"such as: {examples}."
        )
    return column


def _log_df_stats(name: str, df: pd.DataFrame, start: float) -> None:
    elapsed = time.perf_counter() - start
    rows = int(len(df))
    mem_bytes = int(df.memory_usage(deep=True).sum()) if not df.empty else 0
    logger.info(
        "report %s rows=%s mem=%.2fMB elapsed=%.3fs",
        name,
        rows,
        mem_bytes / (1024 * 1024),
        elapsed,
    )


def _min_value_for_metric(column: str) -> Optional[float]:
    if column.startswith("run") and column.endswith("_time_min"):
        return 1.0
    return None


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


def _build_histogram_with_locations(
    values: pd.Series,
    locations: pd.Series,
    *,
    bins: int = 22,
    athlete_value: Optional[float] = None,
    min_value: Optional[float] = None,
) -> Optional[dict]:
    df = pd.DataFrame({"value": values, "location": locations})
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    if min_value is not None:
        df = df[df["value"] >= min_value]
    if df.empty:
        return None
    clean_values = df["value"]
    athlete_percentile = None
    if athlete_value is not None:
        try:
            athlete_value = float(athlete_value)
        except (TypeError, ValueError):
            athlete_value = None
    if min_value is not None and athlete_value is not None and athlete_value < min_value:
        athlete_value = None
    if athlete_value is not None:
        if clean_values.shape[0] == 1:
            athlete_percentile = 1.0
        else:
            rank = int((clean_values < athlete_value).sum()) + 1
            athlete_percentile = 1.0 - (rank - 1) / (clean_values.shape[0] - 1)
    min_val = float(clean_values.min())
    max_val = float(clean_values.max())
    if min_val == max_val:
        max_val = min_val + 1.0
    counts, edges = np.histogram(
        clean_values.to_numpy(), bins=bins, range=(min_val, max_val)
    )
    bin_index = np.searchsorted(edges, clean_values.to_numpy(), side="right") - 1
    bin_index = np.clip(bin_index, 0, len(edges) - 2)
    df = df.assign(bin_index=bin_index)
    location_map = (
        df.groupby("bin_index")["location"]
        .apply(
            lambda series: sorted(
                {str(value).strip() for value in series.dropna() if str(value).strip()},
                key=lambda value: value.casefold(),
            )
        )
        .to_dict()
    )
    buckets = []
    for index in range(len(counts)):
        buckets.append(
            {
                "start": float(edges[index]),
                "end": float(edges[index + 1]),
                "count": int(counts[index]),
                "locations": location_map.get(index, []),
            }
        )
    return {
        "bins": buckets,
        "min": min_val,
        "max": max_val,
        "count": int(clean_values.shape[0]),
        "athlete_value": athlete_value,
        "athlete_percentile": athlete_percentile,
    }



class ReportingClient:
    """
    Thin reporting layer that wires PyroxClient into DuckDB for fast analytics.

    Example:
        >>> from pyrox.reporting import ReportingClient
        >>> reporting = ReportingClient()
        >>> reporting.load_race_table(season=8, location="London")
        'race'
        >>> reporting.query("SELECT COUNT(*) AS n FROM race").iloc[0]["n"] >= 1
        True
    """

    def __init__(
        self,
        client: Optional[PyroxClient] = None,
        database: Optional[str] = None,
    ) -> None:
        self.client = client or PyroxClient()
        self.database = database or ":memory:"
        self._connection = None

    def _ensure_connection(self):
        """
        Lazily create and return the DuckDB connection.

        Example:
            >>> reporting = ReportingClient()
            >>> con = reporting._ensure_connection()
            >>> con.execute("SELECT 1").fetchone()[0]
            1
        """
        if self._connection is None:
            # forcing to be read only!
            read_only = self.database != ":memory:"
            self._connection = duckdb.connect(self.database, read_only=read_only)
        return self._connection


    def search_athlete_races(
        self,
        athlete_name: str,
        *,
        match: str = "best",
        gender: Optional[str] = None,
        division: Optional[str] = None,
        nationality: Optional[str] = None,
        require_unique: bool = True,
    ) -> pd.DataFrame:
        """
        Search the DuckDB athlete index and return a DataFrame of all race rows.

        Args:
            athlete_name: Athlete name to search for.
            match: "best" (exact then contains), "exact", or "contains".
            gender: Optional gender filter for athlete disambiguation.
            nationality: Optional nationality filter for athlete disambiguation.
            division: Optional division filter applied to race results.
            require_unique: Raise if multiple athletes match the search.

        Notes:
            Matching is token-based, so punctuation and name order are ignored.
        """
        if athlete_name is None or str(athlete_name).strip() == "":
            raise ValueError("athlete_name must be a non-empty string.")

        def normalise_tokens(value: str) -> list[str]:
            cleaned = re.sub(r"[^\w]+", " ", value.casefold())
            return [token for token in cleaned.split() if token]

        def split_partners(value: str) -> list[str]:
            raw = value.strip()
            if not raw:
                return []
            parts = re.split(r"\s*(?:/|&|\+|\band\b|\bx\b|\|)\s*", raw)
            parts = [part.strip() for part in parts if part.strip()]
            if len(parts) > 1:
                return parts
            if "," in raw:
                comma_parts = [part.strip() for part in raw.split(",") if part.strip()]
                if len(comma_parts) > 1:
                    counts = [len(normalise_tokens(part)) for part in comma_parts]
                    if counts and all(count >= 2 for count in counts):
                        return comma_parts
            return [raw]

        raw_name = str(athlete_name).strip()
        tokens = normalise_tokens(raw_name)
        if not tokens:
            raise ValueError("athlete_name must include at least one token.")

        input_signature = tuple(sorted(tokens))
        input_token_set = set(tokens)
        match = match.lower()
        if match not in {"best", "exact", "contains"}:
            raise ValueError("match must be one of: 'best', 'exact', 'contains'.")

        if division is not None:
            division = str(division).strip()
            if division == "":
                raise ValueError("division must be a non-empty string when provided.")
            division = division.casefold()

        con = self._ensure_connection()

        def fetch_candidates(token_list: list[str]) -> pd.DataFrame:
            clauses = []
            params = []
            for token in token_list:
                clauses.append("name_lc LIKE '%' || ? || '%'")
                params.append(token)

            if gender is not None:
                clauses.append("gender = ?")
                params.append(gender)
            if nationality is not None:
                clauses.append("nationality = ?")
                params.append(nationality)

            where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            sql = f"""
                SELECT athlete_id, canonical_name, gender, nationality, race_count
                FROM athlete_index
                {where_sql}
                ORDER BY race_count DESC, canonical_name
            """
            return con.execute(sql, params).fetchdf()

        def segment_tokens(value: object) -> list[list[str]]:
            if value is None:
                return []
            segments = split_partners(str(value))
            tokens_list = [normalise_tokens(segment) for segment in segments]
            return [segment for segment in tokens_list if segment]

        def has_exact_match(value: object) -> bool:
            for segment in segment_tokens(value):
                if tuple(sorted(segment)) == input_signature:
                    return True
            return False

        def has_contains_match(value: object) -> bool:
            for segment in segment_tokens(value):
                if input_token_set.issubset(set(segment)):
                    return True
            return False

        candidates = fetch_candidates(tokens)
        if candidates.empty:
            raise AthleteNotFound(f"No athlete match for '{athlete_name}'.")

        exact_mask = candidates["canonical_name"].apply(has_exact_match)
        contains_mask = candidates["canonical_name"].apply(has_contains_match)
        if match == "exact":
            candidates = candidates[exact_mask]
        elif match == "contains":
            candidates = candidates[contains_mask]
        elif match == "best":
            candidates = candidates[exact_mask] if exact_mask.any() else candidates[contains_mask]

        if candidates.empty:
            raise AthleteNotFound(f"No athlete match for '{athlete_name}'.")

        if require_unique and len(candidates) > 1:
            preview = candidates.head(5)
            labels = ", ".join(
                f"{row['canonical_name']} ({row['gender'] or 'unknown'}, "
                f"{row['nationality'] or 'unknown'})"
                for _, row in preview.iterrows()
            )
            raise ValueError(
                "Multiple athletes matched the search. "
                "Refine with gender/nationality/division or set require_unique=False. "
                f"Matches: {labels}"
            )

        athlete_ids = candidates["athlete_id"].dropna().unique().tolist()
        if not athlete_ids:
            raise AthleteNotFound(f"No athlete match for '{athlete_name}'.")

        placeholders = ", ".join(["?"] * len(athlete_ids))
        division_clause = ""
        params = list(athlete_ids)
        if division is not None:
            division_clause = " AND lower(r.division) = ?"
            params.append(division)
        results = con.execute(
            f"""
            SELECT r.*
            FROM race_results r
            JOIN athlete_results ar ON ar.result_id = r.result_id
            WHERE ar.athlete_id IN ({placeholders}){division_clause}
            ORDER BY r.season, r.year, r.location, r.event_id
            """,
            params,
        ).fetchdf()

        if results.empty:
            raise AthleteNotFound(f"No races found for '{athlete_name}'.")
        return results.reset_index(drop=True)

    def race_report(
        self,
        result_id: str,
        *,
        cohort_time_window_min: Optional[float] = 5.0,
    ) -> dict[str, pd.DataFrame]:
        """
        Build a race report bundle for a single result_id.

        Returns:
            dict with keys:
              - race: single-row race_results + race_rankings fields
              - cohort: all results in the same location/division/gender/age_group
              - splits: split_percentiles rows for the athlete result (includes
                split_percentile_time_window when time-window cohort is enabled)
              - cohort_splits: split_percentiles rows for the cohort (location-level)
              - cohort_time_window: results in the same location/season within the
                +/- time window around the athlete total_time_min (when enabled)
              - cohort_time_window_splits: split_percentiles rows for the
                time-window cohort (when enabled)

        Set cohort_time_window_min=None to skip building the time-window cohorts.
        """
        if result_id is None or str(result_id).strip() == "":
            raise ValueError("result_id must be a non-empty string.")

        time_window_min = None
        if cohort_time_window_min is not None:
            try:
                time_window_min = float(cohort_time_window_min)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "cohort_time_window_min must be a positive number when provided."
                ) from exc
            if time_window_min <= 0:
                raise ValueError("cohort_time_window_min must be a positive number when provided.")

        con = self._ensure_connection()
        start = time.perf_counter()
        race = con.execute(
            """
            SELECT
                r.*,
                rr.event_rank,
                rr.event_size,
                rr.event_percentile,
                rr.season_rank,
                rr.season_size,
                rr.season_percentile,
                rr.overall_rank,
                rr.overall_size,
                rr.overall_percentile
            FROM race_results r
            LEFT JOIN race_rankings rr ON rr.result_id = r.result_id
            WHERE r.result_id = ?
            """,
            [result_id],
        ).fetchdf()
        _log_df_stats("race", race, start)

        if race.empty:
            raise ValueError(f"result_id not found: {result_id}")

        start = time.perf_counter()
        cohort = con.execute(
            """
            WITH picked AS (
                SELECT location, division, gender, age_group
                FROM race_results
                WHERE result_id = ?
            )
            SELECT
                r.*,
                rr.event_rank,
                rr.event_size,
                rr.event_percentile
            FROM race_results r
            LEFT JOIN race_rankings rr ON rr.result_id = r.result_id
            JOIN picked p
              ON r.location IS NOT DISTINCT FROM p.location
             AND r.division IS NOT DISTINCT FROM p.division
             AND r.gender IS NOT DISTINCT FROM p.gender
             AND r.age_group IS NOT DISTINCT FROM p.age_group
            ORDER BY r.total_time_min
            """,
            [result_id],
        ).fetchdf()
        _log_df_stats("cohort", cohort, start)

        start = time.perf_counter()
        splits = con.execute(
            """
            SELECT split_name, split_time_min, split_rank, split_size, split_percentile
            FROM split_percentiles
            WHERE result_id = ?
            ORDER BY split_name
            """,
            [result_id],
        ).fetchdf()
        _log_df_stats("splits", splits, start)

        start = time.perf_counter()
        cohort_splits = con.execute(
            """
            WITH picked AS (
                SELECT location, division, gender, age_group
                FROM race_results
                WHERE result_id = ?
            )
            SELECT sp.*
            FROM split_percentiles sp
            JOIN picked p
              ON sp.location IS NOT DISTINCT FROM p.location
             AND sp.division IS NOT DISTINCT FROM p.division
             AND sp.gender IS NOT DISTINCT FROM p.gender
             AND sp.age_group IS NOT DISTINCT FROM p.age_group
            ORDER BY sp.split_name, sp.split_time_min
            """,
            [result_id],
        ).fetchdf()
        _log_df_stats("cohort_splits", cohort_splits, start)

        if time_window_min is not None:
            if "total_time_min" not in race.columns:
                raise ValueError("total_time_min is required to build the time-window cohort.")
            if "season" not in race.columns:
                raise ValueError("season is required to build the time-window cohort.")
            athlete_total_time = race["total_time_min"].iloc[0]
            if athlete_total_time is None or pd.isna(athlete_total_time):
                raise ValueError(f"No total_time_min data for result_id: {result_id}")

            athlete_location = race["location"].iloc[0]
            athlete_season = race["season"].iloc[0]
            if athlete_season is None or pd.isna(athlete_season):
                raise ValueError(f"No season data for result_id: {result_id}")
            athlete_season = int(athlete_season)
            lower_bound = float(athlete_total_time - time_window_min)
            upper_bound = float(athlete_total_time + time_window_min)

            start = time.perf_counter()
            cohort_time_window = con.execute(
                """
                SELECT
                    r.*,
                    rr.event_rank,
                    rr.event_size,
                    rr.event_percentile
                FROM race_results r
                LEFT JOIN race_rankings rr ON rr.result_id = r.result_id
                WHERE r.location IS NOT DISTINCT FROM ?
                  AND r.season IS NOT DISTINCT FROM ?
                  AND r.total_time_min IS NOT NULL
                  AND r.total_time_min BETWEEN ? AND ?
                ORDER BY r.total_time_min
                """,
                [athlete_location, athlete_season, lower_bound, upper_bound],
            ).fetchdf()
            _log_df_stats("cohort_time_window", cohort_time_window, start)

            start = time.perf_counter()
            cohort_time_window_splits = con.execute(
                """
                WITH cohort AS (
                    SELECT result_id
                    FROM race_results
                    WHERE location IS NOT DISTINCT FROM ?
                      AND season IS NOT DISTINCT FROM ?
                      AND total_time_min IS NOT NULL
                      AND total_time_min BETWEEN ? AND ?
                )
                SELECT sp.*
                FROM split_percentiles sp
                JOIN cohort c ON sp.result_id = c.result_id
                ORDER BY sp.split_name, sp.split_time_min
                """,
                [athlete_location, athlete_season, lower_bound, upper_bound],
            ).fetchdf()
            _log_df_stats("cohort_time_window_splits", cohort_time_window_splits, start)

            if not splits.empty:
                start = time.perf_counter()
                percentiles = []
                for _, split_row in splits.iterrows():
                    split_time = split_row["split_time_min"]
                    if split_time is None or pd.isna(split_time):
                        percentiles.append(pd.NA)
                        continue
                    cohort_times = cohort_time_window_splits.loc[
                        cohort_time_window_splits["split_name"] == split_row["split_name"],
                        "split_time_min",
                    ].dropna()
                    cohort_size = len(cohort_times)
                    if cohort_size == 0:
                        percentiles.append(pd.NA)
                        continue
                    if cohort_size == 1:
                        percentiles.append(1.0)
                        continue
                    rank = int((cohort_times < split_time).sum()) + 1
                    percentile = 1.0 - (rank - 1) / (cohort_size - 1)
                    percentiles.append(float(percentile))
                splits = splits.copy()
                splits["split_percentile_time_window"] = percentiles
                logger.info(
                    "report time_window_percentiles rows=%s elapsed=%.3fs",
                    int(len(splits)),
                    time.perf_counter() - start,
                )

        report = {
            "race": race.reset_index(drop=True),
            "cohort": cohort.reset_index(drop=True),
            "splits": splits.reset_index(drop=True),
            "cohort_splits": cohort_splits.reset_index(drop=True),
        }

        if time_window_min is not None:
            report["cohort_time_window"] = cohort_time_window.reset_index(drop=True)
            report["cohort_time_window_splits"] = cohort_time_window_splits.reset_index(
                drop=True
            )

        return report

    def deepdive_location_stats(
        self,
        result_id: str,
        *,
        season: int,
        metric: str = "total_time_min",
        bins: int = 22,
        division: Optional[str] = None,
        gender: Optional[str] = None,
        age_group: Optional[str] = None,
        location: Optional[str] = None,
    ) -> dict[str, object]:
        """
        Build per-location cohort stats for a selected athlete race.

        Season is required. Division/gender/age_group default to the base race
        values but can be overridden.
        """
        if result_id is None or str(result_id).strip() == "":
            raise ValueError("result_id must be a non-empty string.")
        if season is None:
            raise ValueError("season is required for deepdive.")

        metric_column = _resolve_time_column(metric)
        min_value = _min_value_for_metric(metric_column)

        con = self._ensure_connection()
        race = con.execute(
            f"""
            SELECT
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
                {metric_column} AS metric_value
            FROM race_results
            WHERE result_id = ?
            """,
            [result_id],
        ).fetchdf()
        if race.empty:
            raise ValueError(f"result_id not found: {result_id}")

        athlete_value = race["metric_value"].iloc[0]
        if athlete_value is None or pd.isna(athlete_value):
            raise ValueError(f"No {metric_column} data for result_id: {result_id}")

        def pick_override(value: Optional[str], default: object) -> Optional[str]:
            if value is not None and str(value).strip() != "":
                return str(value).strip()
            if default is None or (isinstance(default, float) and pd.isna(default)):
                return None
            text = str(default).strip()
            return text if text else None

        use_division = pick_override(division, race["division"].iloc[0])
        use_gender = pick_override(gender, race["gender"].iloc[0])
        use_age_group = pick_override(age_group, race["age_group"].iloc[0])
        use_location = pick_override(location, None)

        clauses = ["season = ?", f"{metric_column} IS NOT NULL"]
        params: list[object] = [int(season)]

        if use_location is not None:
            clauses.append("lower(location) = ?")
            params.append(use_location.casefold())
        if use_division is not None:
            clauses.append("lower(division) = ?")
            params.append(use_division.casefold())
        if use_gender is not None:
            normalized_gender = use_gender.casefold()
            if normalized_gender in {"m", "male"}:
                clauses.append("lower(gender) IN (?, ?)")
                params.extend(["m", "male"])
            elif normalized_gender in {"f", "female"}:
                clauses.append("lower(gender) IN (?, ?)")
                params.extend(["f", "female"])
            else:
                clauses.append("lower(gender) = ?")
                params.append(normalized_gender)
        if use_age_group is not None:
            clauses.append("lower(age_group) = ?")
            params.append(use_age_group.casefold())

        where_sql = " AND ".join(clauses)
        df = con.execute(
            f"""
            SELECT location, event_id, season, year, {metric_column} AS metric_value
            FROM race_results
            WHERE {where_sql}
            """,
            params,
        ).fetchdf()
        if df.empty:
            raise ValueError("No cohort data found for the selected filters.")

        values = pd.to_numeric(df["metric_value"], errors="coerce").dropna()
        if min_value is not None:
            values = values[values >= min_value]
        if values.empty:
            raise ValueError("No cohort data found for the selected filters.")

        def describe(values_series: pd.Series) -> dict[str, float]:
            return {
                "count": int(values_series.shape[0]),
                "min": float(values_series.min()),
                "max": float(values_series.max()),
                "mean": float(values_series.mean()),
                "median": float(values_series.median()),
            }

        summary_all = describe(values)
        p05_value = float(values.quantile(0.05))
        p90_value = float(values.quantile(0.9))
        top_group = values[values <= p05_value]
        bottom_group = values[values >= p90_value]
        summary_top = describe(top_group) if not top_group.empty else summary_all
        summary_bottom = describe(bottom_group) if not bottom_group.empty else summary_all

        histogram_all = _build_histogram(
            values,
            bins=bins,
            athlete_value=athlete_value,
            min_value=min_value,
        )
        top_athlete = None
        if not top_group.empty:
            top_min = float(top_group.min())
            top_max = float(top_group.max())
            if top_min <= athlete_value <= top_max:
                top_athlete = athlete_value
        histogram_top = (
            _build_histogram_with_locations(
                df.loc[df["metric_value"] <= p05_value, "metric_value"],
                df.loc[df["metric_value"] <= p05_value, "location"],
                bins=bins,
                athlete_value=top_athlete,
                min_value=min_value,
            )
            if not top_group.empty
            else None
        )
        bottom_athlete = None
        if not bottom_group.empty:
            bottom_min = float(bottom_group.min())
            bottom_max = float(bottom_group.max())
            if bottom_min <= athlete_value <= bottom_max:
                bottom_athlete = athlete_value
        histogram_bottom = _build_histogram(
            bottom_group,
            bins=bins,
            athlete_value=bottom_athlete,
            min_value=min_value,
        ) if not bottom_group.empty else None

        rows = []
        for location_label, group in df.groupby("location", dropna=False):
            times = pd.to_numeric(group["metric_value"], errors="coerce").dropna()
            if min_value is not None:
                times = times[times >= min_value]
            if times.empty:
                continue
            seasons = sorted(
                {int(value) for value in group["season"].dropna().tolist() if str(value)}
            )
            years = sorted({int(value) for value in group["year"].dropna().tolist() if str(value)})
            rows.append(
                {
                    "location": location_label,
                    "count": int(times.shape[0]),
                    "seasons": seasons,
                    "years": years,
                    "fastest": float(times.min()),
                    "mean": float(times.mean()),
                    "p05": float(times.quantile(0.05)),
                    "p50": float(times.quantile(0.5)),
                    "p90": float(times.quantile(0.9)),
                }
            )

        locations = pd.DataFrame(rows)
        if locations.empty:
            raise ValueError("No cohort data found for the selected filters.")

        return {
            "race": race.reset_index(drop=True),
            "locations": locations.reset_index(drop=True),
            "total_rows": int(values.shape[0]),
            "total_locations": int(len(locations)),
            "athlete_value": float(athlete_value),
            "metric": metric_column,
            "summary": {
                **summary_all,
                "p05": p05_value,
                "p90": p90_value,
            },
            "group_summary": {
                "mean": summary_all,
                "p05": summary_top,
                "p90": summary_bottom,
            },
            "distribution": histogram_all,
            "group_distribution": {
                "mean": histogram_all,
                "p05": histogram_top,
                "p90": histogram_bottom,
            },
            "filters": {
                "season": int(season),
                "division": use_division,
                "gender": use_gender,
                "age_group": use_age_group,
                "location": use_location,
            },
        }

    def deepdive_filter_options(
        self,
        *,
        season: int,
        division: Optional[str] = None,
        gender: Optional[str] = None,
    ) -> dict[str, list[str]]:
        """
        Return distinct location and age_group values for deepdive dropdowns.
        """
        if season is None:
            raise ValueError("season is required for deepdive filters.")

        clauses = ["season = ?"]
        params: list[object] = [int(season)]

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

        where_sql = " AND ".join(clauses)
        con = self._ensure_connection()
        locations = con.execute(
            f"SELECT DISTINCT location FROM race_results WHERE {where_sql}",
            params,
        ).fetchdf()
        age_groups = con.execute(
            f"SELECT DISTINCT age_group FROM race_results WHERE {where_sql}",
            params,
        ).fetchdf()

        def clean_values(df: pd.DataFrame, column: str) -> list[str]:
            if df.empty or column not in df.columns:
                return []
            values = (
                df[column]
                .dropna()
                .astype(str)
                .map(str.strip)
                .loc[lambda s: s != ""]
                .unique()
                .tolist()
            )
            return sorted(values, key=lambda value: value.casefold())

        return {
            "locations": clean_values(locations, "location"),
            "age_groups": clean_values(age_groups, "age_group"),
        }

    def plot_cohort_distribution(
        self,
        result_id: str,
        metric: str,
        *,
        bins: int = 30,
        cohort_mode: str = "demographic",
        cohort_time_window_min: float = 5.0,
    ) -> Tuple[object, object]:
        """
        Plot the cohort distribution for a metric and mark the athlete value.

        Cohort scope matches race_report (demographic or time-window).
        Use cohort_mode="time_window" to compare against athletes within the
        +/- time window of total_time_min for the same location/season.
        """
        if result_id is None or str(result_id).strip() == "":
            raise ValueError("result_id must be a non-empty string.")

        cohort_mode = str(cohort_mode).strip().casefold()
        if cohort_mode not in {"demographic", "time_window"}:
            raise ValueError("cohort_mode must be 'demographic' or 'time_window'.")

        time_window_min = None
        if cohort_mode == "time_window":
            try:
                time_window_min = float(cohort_time_window_min)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "cohort_time_window_min must be a positive number when cohort_mode is"
                    " 'time_window'."
                ) from exc
            if time_window_min <= 0:
                raise ValueError(
                    "cohort_time_window_min must be a positive number when cohort_mode is"
                    " 'time_window'."
                )

        time_column = _resolve_time_column(metric)
        con = self._ensure_connection()
        athlete = con.execute(
            f"""
            SELECT
                location,
                season,
                division,
                gender,
                age_group,
                total_time_min,
                {time_column} AS athlete_time
            FROM race_results
            WHERE result_id = ?
            """,
            [result_id],
        ).fetchdf()

        if athlete.empty:
            raise ValueError(f"result_id not found: {result_id}")

        athlete_time = athlete["athlete_time"].iloc[0]
        if athlete_time is None or pd.isna(athlete_time):
            raise ValueError(f"No {time_column} data for result_id: {result_id}")

        athlete_location = athlete["location"].iloc[0]
        athlete_season = athlete["season"].iloc[0]
        if athlete_season is None or pd.isna(athlete_season):
            raise ValueError(f"No season data for result_id: {result_id}")
        athlete_season = int(athlete_season)

        if cohort_mode == "demographic":
            athlete_division = athlete["division"].iloc[0]
            athlete_gender = athlete["gender"].iloc[0]
            athlete_ag = athlete["age_group"].iloc[0]
            cohort_times = con.execute(
                f"""
                SELECT {time_column} AS time_value
                FROM race_results
                WHERE location IS NOT DISTINCT FROM ?
                  AND division IS NOT DISTINCT FROM ?
                  AND gender IS NOT DISTINCT FROM ?
                  AND age_group IS NOT DISTINCT FROM ?
                  AND {time_column} IS NOT NULL
                """,
                [
                    athlete_location,
                    athlete_division,
                    athlete_gender,
                    athlete_ag,
                ],
            ).fetchdf()
            cohort_label = f"{athlete_division} - {athlete_gender} - {athlete_ag}"
        else:
            if "total_time_min" not in athlete.columns:
                raise ValueError("total_time_min is required to build the time-window cohort.")
            athlete_total_time = athlete["total_time_min"].iloc[0]
            if athlete_total_time is None or pd.isna(athlete_total_time):
                raise ValueError(f"No total_time_min data for result_id: {result_id}")
            lower_bound = float(athlete_total_time - time_window_min)
            upper_bound = float(athlete_total_time + time_window_min)
            cohort_times = con.execute(
                f"""
                SELECT {time_column} AS time_value
                FROM race_results
                WHERE location IS NOT DISTINCT FROM ?
                  AND season IS NOT DISTINCT FROM ?
                  AND total_time_min IS NOT NULL
                  AND total_time_min BETWEEN ? AND ?
                  AND {time_column} IS NOT NULL
                """,
                [athlete_location, athlete_season, lower_bound, upper_bound],
            ).fetchdf()
            window_label = f"+/-{time_window_min:g}m total_time"
            cohort_label = f"{athlete_location} - season {athlete_season} - {window_label}"

        if cohort_times.empty:
            raise ValueError("No cohort data found for the selected race.")

        from matplotlib import pyplot as plt
        import seaborn as sns

        sns.set_style("darkgrid")

        fig, ax = plt.subplots()
        ax.hist(cohort_times["time_value"], bins=bins, color="#5B8FF9", alpha=0.8)
        ax.axvline(
            athlete_time,
            color="#D62728",
            linestyle="--",
            linewidth=2,
            label="athlete",
        )
        ax.set_title(f"{time_column} distribution - {cohort_label}")
        ax.set_xlabel(f"{time_column} (minutes)")
        ax.set_ylabel("count")
        ax.legend()

        return fig, ax

    def query(self, sql: str, params: Optional[Iterable[object]] = None) -> pd.DataFrame:
        """
        Run a DuckDB query and return the result as a DataFrame.

        Example:
            >>> reporting = ReportingClient()
            >>> reporting.query("SELECT 1 AS value")["value"][0]
            1
        """
        con = self._ensure_connection()
        if params is None:
            return con.execute(sql).fetchdf()
        return con.execute(sql, params).fetchdf()
