"""
Reporting helpers for PyroxClient with DuckDB integration.
"""

from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd

from .core import PyroxClient

import duckdb


def build_athlete_options(
    df: pd.DataFrame,
    query: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict[str, object]]:
    """
    Build a list of athlete options for UI selection.

    Returns a list of dicts: {"value": name, "label": name, "count": n}.

    Example:
        >>> import pandas as pd
        >>> from pyrox.repor=ting import build_athlete_options
        >>> df = pd.DataFrame({"name": ["Alex", "Alex", "Blake"]})
        >>> build_athlete_options(df)
        [{'value': 'Alex', 'label': 'Alex', 'count': 2}, {'value': 'Blake', 'label': 'Blake', 'count': 1}]
    """
    if "name" not in df.columns:
        raise KeyError("Column 'name' not found in race data.")

    names = df["name"].dropna().astype(str).str.strip()
    names = names[names != ""]
    counts = names.value_counts()

    if query:
        mask = counts.index.str.contains(query, case=False, regex=False)
        counts = counts[mask]

    if limit is not None:
        counts = counts.head(int(limit))

    options = [
        {"value": name, "label": name, "count": int(count)}
        for name, count in counts.items()
    ]
    return options


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

    def register_dataframe(self, name: str, df: pd.DataFrame) -> None:
        """
        Register a pandas DataFrame as a DuckDB table.

        Example:
            >>> import pandas as pd
            >>> reporting = ReportingClient()
            >>> reporting.register_dataframe("demo", pd.DataFrame({"x": [1, 2]}))
            >>> reporting.query("SELECT SUM(x) AS total FROM demo")["total"][0]
            3
        """
        con = self._ensure_connection()
        con.register(name, df)

    def load_race_table(
        self,
        season: int,
        location: str,
        year: Optional[int] = None,
        gender: Optional[str] = None,
        division: Optional[str] = None,
        total_time: Optional[float | tuple[Optional[float], Optional[float]]] = None,
        table_name: str = "race",
    ) -> str:
        """
        Fetch a race from the CDN/cache and register it as a DuckDB table.

        Example:
            >>> reporting = ReportingClient()
            >>> reporting.load_race_table(season=8, location="London", table_name="race8")
            'race8'
        """
        df = self.client.get_race(
            season=season,
            location=location,
            year=year,
            gender=gender,
            division=division,
            total_time=total_time,
        )
        self.register_dataframe(table_name, df)
        return table_name

    def load_season_table(
        self,
        season: int,
        locations: Optional[Iterable[str]] = None,
        gender: Optional[str] = None,
        division: Optional[str] = None,
        table_name: str = "season",
    ) -> str:
        """
        Fetch a season across locations and register it as a DuckDB table.

        Example:
            >>> reporting = ReportingClient()
            >>> reporting.load_season_table(season=8, table_name="season8")
            'season8'
        """
        df = self.client.get_season(
            season=season,
            locations=locations,
            gender=gender,
            division=division,
        )
        self.register_dataframe(table_name, df)
        return table_name

    def list_athletes(
        self,
        season: int,
        location: str,
        year: Optional[int] = None,
        gender: Optional[str] = None,
        division: Optional[str] = None,
        query: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, object]]:
        """
        Return UI-friendly athlete options for a race.

        Example:
            >>> reporting = ReportingClient()
            >>> options = reporting.list_athletes(season=8, location="London", query="ali", limit=5)
            >>> isinstance(options, list)
            True
        """
        df = self.client.get_race(
            season=season,
            location=location,
            year=year,
            gender=gender,
            division=division,
        )
        return build_athlete_options(df, query=query, limit=limit)

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
