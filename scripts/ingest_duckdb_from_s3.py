from __future__ import annotations


from dotenv import load_dotenv
load_dotenv()
import os
import duckdb
import logging
from sql_queries import MACRO, CREATE_RACE_RESULTS

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ingest_duckdb")

def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"Missing required env var: {name}")
    return value.strip()


# ------ Config ------

DUCKDB_PATH = required_env("DUCKDB_PATH")  # e.g. "/data/analytics.duckdb"
DUCKDB_TMP_PATH = DUCKDB_PATH + ".new"

S3_URI = required_env("S3_URI")  # e.g. "s3://my-bucket/processed/parquet/season=*/**/*.parquet"
S3_REGION = required_env("S3_REGION")  

AWS_ACCESS_KEY_ID = required_env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = required_env("AWS_SECRET_ACCESS_KEY")


# -----------
# DuckDB / S3 setup
# -----------
def configure_s3(con: duckdb.DuckDBPyConnection) -> None:
    """
    Enabe DuckDB to read from s3://URIs
    
    :param con: connection object
    :type con: duckdb.DuckDBPyConnection
    """
    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")
    con.execute(f"SET s3_region='{S3_REGION}';")
    con.execute(f"SET s3_access_key_id='{AWS_ACCESS_KEY_ID}';")
    con.execute(f"SET s3_secret_access_key='{AWS_SECRET_ACCESS_KEY}';")


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

    logger.info("Starting full refresh ingest...")
    logger.info(f"Reading from S3 URI: {S3_URI}")
    logger.info(f"Writing to DuckDB path: {DUCKDB_PATH}")

    con = duckdb.connect(DUCKDB_TMP_PATH)
    configure_s3(con)

    logger.info("Reading data from S3...")
    con.execute("BEGIN TRANSACTION;")

    con.execute(MACRO)


    con.execute(CREATE_RACE_RESULTS)


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
         AND coalesce(a.nationality, '') = coalesce(r.nationality, '');
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
            AVG(r.total_time_s) AS avg_total_time,
            AVG(r.run_time_s / NULLIF(r.total_time_s, 0)) AS avg_run_ratio

        FROM athletes a
        JOIN athlete_results ar ON a.athlete_id = ar.athlete_id
        JOIN race_results r ON r.result_id = ar.result_id
        GROUP BY 1,2,3,4,5;
        """
    )

    con.execute("COMMIT;")
    con.close()


    # atomic swap into place
    os.replace(DUCKDB_TMP_PATH, DUCKDB_PATH)

    logger.info(F"Ingestion Complete - {DUCKDB_PATH}")

    
if __name__ == "__main__":
    ingest_full_refresh()
