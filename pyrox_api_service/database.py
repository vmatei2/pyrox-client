"""DuckDB runtime access for the repository-local reporting service.

This module owns the service's database configuration seam: resolving the
runtime DuckDB artifact, constructing the repository's existing
``ReportingClient``, and exposing small health-check operations. It deliberately
models the concrete DuckDB runtime instead of a generic database abstraction,
because DuckDB is the only production adapter today.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:  # Prefer installed package imports.
    from pyrox.reporting import ReportingClient
except ModuleNotFoundError:  # pragma: no cover - direct repository execution fallback
    from src.pyrox.reporting import ReportingClient


DEFAULT_DB_PATH = "pyrox_duckdb"
DUCKDB_PATH_ENV = "PYROX_DUCKDB_PATH"


class DatabaseConfigurationError(RuntimeError):
    """Raised when the configured DuckDB artifact cannot be resolved or opened."""


def resolve_database_path(
    raw: Optional[str] = None,
    *,
    cwd: Optional[Path] = None,
) -> str:
    """Return the concrete DuckDB path the reporting service should open.

    Args:
        raw: Optional explicit path. When omitted, ``PYROX_DUCKDB_PATH`` is read
            from the environment and falls back to ``pyrox_duckdb``.
        cwd: Base directory for relative paths. Defaults to the process working
            directory.

    Returns:
        ``":memory:"`` unchanged, or an absolute filesystem path as a string.

    Raises:
        DatabaseConfigurationError: If the resolved path does not exist.
    """
    value = raw if raw is not None else os.getenv(DUCKDB_PATH_ENV, DEFAULT_DB_PATH)
    if value == ":memory:":
        return value

    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (cwd or Path.cwd()) / path
    if not path.exists():
        raise DatabaseConfigurationError(
            f"DuckDB file not found at '{path}'. Set {DUCKDB_PATH_ENV} to a valid path."
        )
    return str(path)


@dataclass(frozen=True)
class DuckDBRuntime:
    """Concrete runtime seam for the DuckDB-backed reporting data artifact.

    The runtime hides how callers obtain a read-only DuckDB connection. It does
    not cache connections itself; ``ReportingClient`` keeps the connection
    lifecycle used by the existing reporting implementation.
    """

    database_path: str

    @classmethod
    def from_env(cls) -> "DuckDBRuntime":
        """Build a runtime from the current process environment."""
        return cls(database_path=resolve_database_path())

    def reporting_client(self) -> ReportingClient:
        """Create a ``ReportingClient`` pointed at this runtime's DuckDB file."""
        return ReportingClient(database=self.database_path)

    def connection(self):
        """Return a DuckDB connection through ``ReportingClient``.

        The returned object is the existing DuckDB connection type used by
        ``pyrox.reporting``. For on-disk databases, the underlying client opens
        the file read-only.
        """
        return self.reporting_client()._ensure_connection()

    def list_tables(self) -> list[str]:
        """Return table names visible in the configured DuckDB artifact."""
        con = self.connection()
        return [row[0] for row in con.execute("SHOW TABLES").fetchall()]


def get_runtime() -> DuckDBRuntime:
    """Return the default runtime for request handling."""
    return DuckDBRuntime.from_env()
