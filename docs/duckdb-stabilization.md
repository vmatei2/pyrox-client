# DuckDB Stabilization Tasks
- Define schema contracts for `race_results`, `athletes`, `athlete_results`, and `athlete_index`
- Add a `metadata` table with schema_version, build timestamp, and data source info
- Store the hash/version of `scripts/sql_queries.py` and ingest macro in `metadata`
- Validate ingest output (tables exist, required columns, non-zero row counts)
- Add a client-side health check for schema_version mismatch
- Build a minimal fixture DuckDB for tests (singles + doubles cases)
- Document required env vars and lock behavior (read-only vs read-write)

## Remote DuckDB Usage Options
- Publish the `.duckdb` file to object storage and download/cache locally
- Query Parquet directly from S3 (no DB file; requires on-the-fly views)
- Use a hosted DuckDB service (e.g., MotherDuck) for multi-user access
- Use a database server (Postgres/ClickHouse) if concurrent writes are needed

## Schema Contracts (v1)
Source of truth: `scripts/sql_queries.py` and `scripts/ingest_duckdb_from_s3.py`.

### race_results
Built from S3 parquet via `CREATE_RACE_RESULTS`. Non-nullable fields are required for
stable keys and search; other fields may be NULL depending on source data.

- Keys and required fields:
  - `result_id` VARCHAR NOT NULL (deterministic md5, primary key)
  - `season` INTEGER NOT NULL
  - `location` VARCHAR NOT NULL (lowercased)
  - `year` INTEGER NOT NULL
  - `event_id` VARCHAR NOT NULL
  - `name` VARCHAR NOT NULL (trimmed)
- Nullable attributes:
  - `age_group` VARCHAR
  - `division` VARCHAR
  - `event_name` VARCHAR
  - `gender` VARCHAR
  - `name_raw` VARCHAR
  - `nationality` VARCHAR
- Time string columns (VARCHAR, nullable):
  - `roxzone_time`
  - `run1_time`, `run2_time`, `run3_time`, `run4_time`,
    `run5_time`, `run6_time`, `run7_time`, `run8_time`
  - `run_time`, `total_time`
  - `skiErg_time`, `sledPush_time`, `sledPull_time`, `burpeeBroadJump_time`,
    `rowErg_time`, `farmersCarry_time`, `sandbagLunges_time`, `wallBalls_time`
  - `work_time`
- Time numeric columns (DOUBLE, nullable; minutes):
  - `roxzone_time_min`
  - `run1_time_min`, `run2_time_min`, `run3_time_min`, `run4_time_min`,
    `run5_time_min`, `run6_time_min`, `run7_time_min`, `run8_time_min`
  - `run_time_min`, `total_time_min`
  - `skiErg_time_min`, `sledPush_time_min`, `sledPull_time_min`,
    `burpeeBroadJump_time_min`, `rowErg_time_min`, `farmersCarry_time_min`,
    `sandbagLunges_time_min`, `wallBalls_time_min`
  - `work_time_min`

### athletes
Derived from `race_results` (canonical identity).

- Columns:
  - `athlete_id` VARCHAR NOT NULL (md5 of canonical_name|gender|nationality, primary key)
  - `canonical_name` VARCHAR NOT NULL (lower(trim(name_raw)))
  - `gender` VARCHAR
  - `nationality` VARCHAR

### athlete_results
Link table between athletes and race results.

- Columns:
  - `athlete_id` VARCHAR NOT NULL (FK to athletes.athlete_id)
  - `result_id` VARCHAR NOT NULL (FK to race_results.result_id)
  - `link_confidence` DOUBLE NOT NULL (currently 1.0 for exact match)
  - `link_method` VARCHAR NOT NULL (currently "exact_key")
- Constraints:
  - Composite primary key (`athlete_id`, `result_id`)

### athlete_index
Pre-aggregated search index for fast lookup.

- Columns:
  - `athlete_id` VARCHAR NOT NULL (FK to athletes.athlete_id)
  - `canonical_name` VARCHAR NOT NULL
  - `name_lc` VARCHAR NOT NULL (lower(canonical_name))
  - `gender` VARCHAR
  - `nationality` VARCHAR
  - `race_count` INTEGER NOT NULL
  - `avg_total_time` DOUBLE
  - `avg_run_ratio` DOUBLE
- Constraints:
  - Primary key (`athlete_id`)

## Contract Alignment Notes
- Tests should mirror contract columns (especially `athlete_results` link metadata).
- `race_results.division` is required for client-side filtering in
  `src/pyrox/reporting.py`.
