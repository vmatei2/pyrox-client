# DuckDB Schema Contracts

The database build lives in the upstream `hyrox_analysis` repository
(`scraping_code/db_build/`), which publishes an immutable artifact plus a
`latest.json` pointer to S3. This service downloads and checksum-verifies the
artifact on boot via `pyrox_api_service/fetch_db.py`, and refuses pointers
whose `schema_version` is newer than `fetch_db.SUPPORTED_SCHEMA_VERSION`. The
artifact stamps a `build_info` table (schema_version, built_at, source S3 URI).

## Schema Contracts (v1)
Source of truth: `scraping_code/db_build/sql_queries.py` and
`scraping_code/db_build/ingest.py` in the `hyrox_analysis` repository.

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

## Build Integrity Gate
The upstream DuckDB build refuses to publish an artifact when any
`(season, location, year, division)` group in `race_results` shows
duplicate-roster fan-out: high rows per distinct athlete name within the same
Race and Division. Explicit zero Roxzone values are allowed downstream and do
not block the build. The gate lives beside the scraper in `hyrox_analysis`
and shares its integrity thresholds (`scraping_code/integrity.py`).
