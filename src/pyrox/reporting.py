"""
Reporting helpers for PyroxClient with DuckDB integration.
"""

from __future__ import annotations

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
            require_unique: Raise if multiple athletes match the search.
        """
        if athlete_name is None or str(athlete_name).strip() == "":
            raise ValueError("athlete_name must be a non-empty string.")

        name_lc = str(athlete_name).strip().lower()
        match = match.lower()
        if match not in {"best", "exact", "contains"}:
            raise ValueError("match must be one of: 'best', 'exact', 'contains'.")

        con = self._ensure_connection()

        def fetch_candidates(mode: str) -> pd.DataFrame:
            clauses = []
            params = []
            if mode == "exact":
                clauses.append("name_lc = ?")
                params.append(name_lc)
            elif mode == "contains":
                clauses.append("name_lc LIKE '%' || ? || '%'")
                params.append(name_lc)
            else:
                raise ValueError("Unsupported match mode.")

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

        if match == "best":
            candidates = fetch_candidates("exact")
            if candidates.empty:
                candidates = fetch_candidates("contains")
        else:
            candidates = fetch_candidates(match)

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
                "Refine with gender/nationality or set require_unique=False. "
                f"Matches: {labels}"
            )

        # helpful for doubles -- if we are searching for an athlete with a name that is repeated in the db, return all entries for that name
        # rather than just the first one
        athlete_ids = candidates["athlete_id"].dropna().unique().tolist()
        if not athlete_ids:
            raise AthleteNotFound(f"No athlete match for '{athlete_name}'.")

        placeholders = ", ".join(["?"] * len(athlete_ids))
        results = con.execute(
            f"""
            SELECT r.*
            FROM race_results r
            JOIN athlete_results ar ON ar.result_id = r.result_id
            WHERE ar.athlete_id IN ({placeholders})
            ORDER BY r.season, r.year, r.location, r.event_id
            """,
            athlete_ids,
        ).fetchdf()

        if results.empty:
            raise AthleteNotFound(f"No races found for '{athlete_name}'.")
        return results.reset_index(drop=True)

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
