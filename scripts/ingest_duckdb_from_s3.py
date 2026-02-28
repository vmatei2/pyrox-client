from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from datetime import date
from pathlib import Path

import duckdb
from dotenv import load_dotenv

try:
    from .sql_queries import (
        CREATE_ATHLETE_HISTORY,
        CREATE_RACE_RANKINGS,
        CREATE_SPLIT_PERCENTILES,
        MACRO,
        create_race_results_query,
    )
except ImportError:
    from sql_queries import (
        CREATE_ATHLETE_HISTORY,
        CREATE_RACE_RANKINGS,
        CREATE_SPLIT_PERCENTILES,
        MACRO,
        create_race_results_query,
    )

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ingest_duckdb")

START_DATE_FILE_PATTERN = "EVENT_START_DATES_SEASON_*.json"
START_DATE_FILENAME_PATTERN = re.compile(r"^EVENT_START_DATES_SEASON_(?P<season>\d+)\.json$")
EVENT_KEY_PATTERN = re.compile(
    r"^\s*HYROX\s+(?P<city>.+?)\s+(?P<year>20\d{2})(?:\s*/.*)?\s*$",
    re.IGNORECASE,
)

DB_LOCATION_ALIASES = {
    "delhi": "new-delhi",
    "gent": "ghent",
    "london-excel": "london",
    "singapore-expo": "singapore",
    "singapore-national-stadium": "singapore",
    "johannesburg-i": "johannesburg",
    "miami-beach": "miami",
    "chicago-navy-pier": "chicago",
    "ciudad-de-mexico": "mexico-city",
    "belgium": "mechelen",
}


def _normalize_location_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.replace(".", " ")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")
    return slug


def _parse_start_date_file_season(path: Path) -> int:
    match = START_DATE_FILENAME_PATTERN.match(path.name)
    if not match:
        raise RuntimeError(f"Invalid start-date filename: {path.name}")
    return int(match.group("season"))


def _parse_event_key(event_name: str) -> tuple[str, int]:
    match = EVENT_KEY_PATTERN.match(event_name.strip())
    if not match:
        raise RuntimeError(f"Unrecognized event key in start-date JSON: {event_name!r}")
    location = _normalize_location_slug(match.group("city").strip())
    year = int(match.group("year"))
    return location, year


def _parse_start_date(value: object, *, context: str) -> date:
    if not isinstance(value, str):
        raise RuntimeError(f"Invalid start_date in {context}: expected string, got {type(value).__name__}")
    date_part = value.split("T", 1)[0].strip()
    try:
        return date.fromisoformat(date_part)
    except ValueError as exc:
        raise RuntimeError(f"Invalid start_date in {context}: {value!r}") from exc


def load_event_start_date_mapping(files_dir: Path | None = None) -> dict[tuple[int, str, int], date]:
    base_dir = files_dir or Path(__file__).resolve().parent
    json_files = sorted(base_dir.glob(START_DATE_FILE_PATTERN))
    if not json_files:
        raise RuntimeError(
            f"No start-date JSON files found in {base_dir} matching {START_DATE_FILE_PATTERN}"
        )

    mapping: dict[tuple[int, str, int], date] = {}

    for path in json_files:
        season = _parse_start_date_file_season(path)
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise RuntimeError(f"Invalid JSON payload in {path}: expected object")

        for event_name, raw_date in payload.items():
            if not isinstance(event_name, str):
                raise RuntimeError(f"Invalid event key in {path}: expected string key")
            location, year = _parse_event_key(event_name)
            start_date = _parse_start_date(raw_date, context=f"{path.name}:{event_name}")
            key = (season, location, year)
            current = mapping.get(key)
            if current is not None and current != start_date:
                raise RuntimeError(
                    "Conflicting start_date mapping for "
                    f"(season={season}, location={location}, year={year}): {current} vs {start_date}"
                )
            mapping[key] = start_date

    return mapping


def _build_alias_map() -> dict[str, str]:
    return {
        _normalize_location_slug(source): _normalize_location_slug(target)
        for source, target in DB_LOCATION_ALIASES.items()
    }


def _build_in_clause_placeholders(values: list[int]) -> str:
    return ", ".join("?" for _ in values)


def apply_event_start_dates(
    con: duckdb.DuckDBPyConnection,
    start_dates: dict[tuple[int, str, int], date],
) -> None:
    if not start_dates:
        raise RuntimeError("No start-date mappings available for ingest.")

    mapped_seasons = sorted({season for season, _, _ in start_dates})
    placeholders = _build_in_clause_placeholders(mapped_seasons)
    alias_map = _build_alias_map()

    db_event_rows = con.execute(
        f"""
        SELECT DISTINCT
            CAST(season AS INTEGER) AS season,
            trim(CAST(location AS VARCHAR)) AS location,
            CAST(year AS INTEGER) AS year
        FROM race_results
        WHERE CAST(season AS INTEGER) IN ({placeholders})
          AND location IS NOT NULL
          AND year IS NOT NULL
        """,
        mapped_seasons,
    ).fetchall()

    resolved_rows: list[tuple[int, str, int, str]] = []
    for season, location, year in db_event_rows:
        normalized_location = _normalize_location_slug(location)
        target_location = alias_map.get(normalized_location, normalized_location)
        start_date = start_dates.get((int(season), target_location, int(year)))
        if start_date is None:
            continue
        resolved_rows.append((int(season), str(location), int(year), start_date.isoformat()))

    con.execute("ALTER TABLE race_results ADD COLUMN start_date DATE;")
    con.execute(
        """
        CREATE TEMP TABLE event_start_dates_resolved (
            season INTEGER,
            location VARCHAR,
            year INTEGER,
            start_date DATE
        );
        """
    )
    if resolved_rows:
        con.executemany(
            "INSERT INTO event_start_dates_resolved VALUES (?, ?, ?, ?);",
            resolved_rows,
        )

    con.execute(
        """
        UPDATE race_results AS r
        SET start_date = m.start_date
        FROM event_start_dates_resolved AS m
        WHERE r.season = m.season
          AND r.location = m.location
          AND r.year = m.year;
        """
    )

    unmapped_rows = con.execute(
        f"""
        SELECT DISTINCT
            CAST(season AS INTEGER) AS season,
            trim(CAST(location AS VARCHAR)) AS location,
            CAST(year AS INTEGER) AS year
        FROM race_results
        WHERE CAST(season AS INTEGER) IN ({placeholders})
          AND start_date IS NULL
        ORDER BY season, year, location
        """,
        mapped_seasons,
    ).fetchall()
    if unmapped_rows:
        sample_rows = []
        for season, location, year in unmapped_rows[:20]:
            normalized_location = _normalize_location_slug(location)
            normalized_target = alias_map.get(normalized_location, normalized_location)
            sample_rows.append((int(season), str(location), int(year), normalized_target))
        raise RuntimeError(
            "Missing start_date mappings for "
            f"{len(unmapped_rows)} distinct event keys. "
            "Sample (season, location, year, normalized_target): "
            f"{sample_rows}"
        )

    mapped_count = con.execute(
        f"""
        SELECT COUNT(*)
        FROM race_results
        WHERE CAST(season AS INTEGER) IN ({placeholders})
          AND start_date IS NOT NULL
        """,
        mapped_seasons,
    ).fetchone()[0]
    logger.info(
        "Applied event start dates for seasons=%s mapped_rows=%s distinct_events=%s",
        mapped_seasons,
        mapped_count,
        len(db_event_rows),
    )


def warn_if_single_season_scope(s3_uri: str) -> None:
    """
    Warn when S3 URI appears scoped to a single season partition.
    """
    match = re.search(r"season=([^/]+)", s3_uri)
    if not match:
        return

    season_selector = match.group(1).strip()
    if season_selector == "*":
        return

    # Wildcards/lists/ranges are treated as multi-season selectors.
    if any(char in season_selector for char in "*?{},[]"):
        return

    logger.warning(
        "S3_URI appears pinned to a single season (%s). "
        "Use season=* to ingest all available seasons.",
        season_selector,
    )

def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"Missing required env var: {name}")
    return value.strip()


def _load_ingest_config() -> dict[str, str]:
    duckdb_path = required_env("DUCKDB_PATH")
    return {
        "duckdb_path": duckdb_path,
        "duckdb_tmp_path": duckdb_path + ".new",
        "s3_uri": required_env("S3_URI"),
        "s3_region": required_env("S3_REGION"),
        "aws_access_key_id": required_env("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": required_env("AWS_SECRET_ACCESS_KEY"),
        "aws_session_token": os.getenv("AWS_SESSION_TOKEN", "").strip(),
    }


# -----------
# DuckDB / S3 setup
# -----------
def configure_s3(con: duckdb.DuckDBPyConnection, config: dict[str, str]) -> None:
    """
    Enabe DuckDB to read from s3://URIs
    
    :param con: connection object
    :type con: duckdb.DuckDBPyConnection
    """
    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")
    con.execute(f"SET s3_region='{config['s3_region']}';")
    con.execute(f"SET s3_access_key_id='{config['aws_access_key_id']}';")
    con.execute(f"SET s3_secret_access_key='{config['aws_secret_access_key']}';")
    if config["aws_session_token"]:
        con.execute(f"SET s3_session_token='{config['aws_session_token']}';")


# -----------
# Ingest
# -----------

def ingest_full_refresh() -> None:
    """
    Full rebuild of DuckDB from latest S3 parquet.

    Notes:
        - Uses columns existing in parquet
        - Creates deterministic IDs (md5) 
        - Builds a basic athlete identity (TODO: replace with probablistic fuzzy linking?)
        - Writes to a temp DB file then automatically swaps into place
    """

    config = _load_ingest_config()
    logger.info("Starting full refresh ingest...")
    logger.info(f"Reading from S3 URI: {config['s3_uri']}")
    logger.info(f"Writing to DuckDB path: {config['duckdb_path']}")
    warn_if_single_season_scope(config["s3_uri"])

    con = duckdb.connect(config["duckdb_tmp_path"])
    configure_s3(con, config)

    logger.info("Reading data from S3...")
    con.execute("BEGIN TRANSACTION;")

    con.execute(MACRO)


    con.execute(create_race_results_query(config["s3_uri"]))
    start_dates = load_event_start_date_mapping()
    apply_event_start_dates(con, start_dates)


    # Optional: basic hygiene (helps later joins/search)
    con.execute(
        """
        UPDATE race_results
        SET name_raw = trim(name_raw)
        WHERE name_raw IS NOT NULL;
        """
    )

    # 2) athletes: canonical identity (v1 exact key)
    # athlete_id is a deterministic md5 hash of (canonical_name, gender, nationality)
    con.execute(
        """
        CREATE OR REPLACE TABLE athletes AS
        WITH base AS (
            SELECT DISTINCT
                lower(trim(name_raw)) AS canonical_name,
                gender,
                nationality,
                md5(
                    lower(trim(name_raw)) || '|' ||
                    coalesce(gender, '') || '|' ||
                    coalesce(nationality, '')
                ) AS athlete_id
            FROM race_results
            WHERE name_raw IS NOT NULL
              AND trim(name_raw) <> ''
        )
        SELECT
            athlete_id,
            canonical_name,
            gender,
            nationality
        FROM base;
        """
    )


    # 3) athlete_results: link layer (v1 exact match)
    con.execute(
        """
        CREATE OR REPLACE TABLE athlete_results AS
        SELECT
            a.athlete_id,
            r.result_id,
            1.0 AS link_confidence,
            'exact_key' AS link_method
        FROM race_results r
        JOIN athletes a
          ON a.canonical_name = lower(trim(r.name_raw))
         AND coalesce(a.gender, '') = coalesce(r.gender, '')
         AND coalesce(a.nationality, '') = coalesce(r.nationality, '')

         ;
        """
    )

    # 4) athlete_index: pre-aggregated search table for fast autocomplete
    con.execute(
        """
        CREATE OR REPLACE TABLE athlete_index AS
        SELECT
            a.athlete_id,
            a.canonical_name,
            lower(a.canonical_name) AS name_lc,
            a.gender,
            a.nationality,
            COUNT(*) AS race_count,

            -- handy "fingerprint" stats for ranking/filtering later
            AVG(r.total_time_min) AS avg_total_time,
            AVG(r.run_time_min / NULLIF(r.total_time_min, 0)) AS avg_run_ratio

        FROM athletes a
        JOIN athlete_results ar ON a.athlete_id = ar.athlete_id
        JOIN race_results r ON r.result_id = ar.result_id
        GROUP BY 1,2,3,4,5;
        """
    )

    # 5) reporting tables for rankings and split percentiles
    con.execute(CREATE_RACE_RANKINGS)
    con.execute(CREATE_SPLIT_PERCENTILES)

    # 6) athlete history enriched with standings
    con.execute(CREATE_ATHLETE_HISTORY)

    con.execute("COMMIT;")
    con.close()


    # atomic swap into place
    os.replace(config["duckdb_tmp_path"], config["duckdb_path"])

    logger.info(F"Ingestion Complete - {config['duckdb_path']}")

    
if __name__ == "__main__":
    ingest_full_refresh()
