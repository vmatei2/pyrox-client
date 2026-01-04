"""
Reporting helpers for PyroxClient with DuckDB integration.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

import duckdb
import pandas as pd

from .core import PyroxClient
from .errors import AthleteNotFound




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
            self._connection = duckdb.connect(self.database)
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

    def race_report(self, result_id: str) -> dict[str, pd.DataFrame]:
        """
        Build a race report bundle for a single result_id.

        Returns:
            dict with keys:
              - race: single-row race_results + race_rankings fields
              - cohort: all results in the same event/division/gender/age_group
              - splits: split_percentiles rows for the athlete result
              - cohort_splits: split_percentiles rows for the cohort
        """
        if result_id is None or str(result_id).strip() == "":
            raise ValueError("result_id must be a non-empty string.")

        con = self._ensure_connection()
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

        if race.empty:
            raise ValueError(f"result_id not found: {result_id}")

        cohort = con.execute(
            """
            WITH picked AS (
                SELECT event_id, division, gender, age_group
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
              ON r.event_id = p.event_id
             AND r.division IS NOT DISTINCT FROM p.division
             AND r.gender IS NOT DISTINCT FROM p.gender
             AND r.age_group IS NOT DISTINCT FROM p.age_group
            ORDER BY r.total_time_min
            """,
            [result_id],
        ).fetchdf()

        splits = con.execute(
            """
            SELECT split_name, split_time_min, split_rank, split_size, split_percentile
            FROM split_percentiles
            WHERE result_id = ?
            ORDER BY split_name
            """,
            [result_id],
        ).fetchdf()

        cohort_splits = con.execute(
            """
            WITH picked AS (
                SELECT event_id, division, gender, age_group
                FROM race_results
                WHERE result_id = ?
            )
            SELECT sp.*
            FROM split_percentiles sp
            JOIN picked p
              ON sp.event_id = p.event_id
             AND sp.division IS NOT DISTINCT FROM p.division
             AND sp.gender IS NOT DISTINCT FROM p.gender
             AND sp.age_group IS NOT DISTINCT FROM p.age_group
            ORDER BY sp.split_name, sp.split_time_min
            """,
            [result_id],
        ).fetchdf()

        return {
            "race": race.reset_index(drop=True),
            "cohort": cohort.reset_index(drop=True),
            "splits": splits.reset_index(drop=True),
            "cohort_splits": cohort_splits.reset_index(drop=True),
        }

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


