MACRO = """
CREATE OR REPLACE MACRO time_to_min(t) AS (
  CASE
    WHEN t IS NULL THEN NULL
    ELSE (
      SELECT
        CASE
          WHEN regexp_matches(cleaned, '^[0-9]+:[0-9]{1,2}:[0-9]{1,2}(\\.[0-9]+)?$') THEN
            (
                3600 * coalesce(try_cast(split_part(cleaned, ':', 1) AS DOUBLE), 0.0)
              +   60 * coalesce(try_cast(split_part(cleaned, ':', 2) AS DOUBLE), 0.0)
              +        coalesce(try_cast(split_part(split_part(cleaned, ':', 3), '.', 1) AS DOUBLE), 0.0)
              +        coalesce(try_cast('0.' || split_part(split_part(cleaned, ':', 3), '.', 2) AS DOUBLE), 0.0)
            ) / 60.0

          WHEN regexp_matches(cleaned, '^[0-9]+:[0-9]{1,2}(\\.[0-9]+)?$') THEN
            (
                 60 * coalesce(try_cast(split_part(cleaned, ':', 1) AS DOUBLE), 0.0)
              +       coalesce(try_cast(split_part(split_part(cleaned, ':', 2), '.', 1) AS DOUBLE), 0.0)
              +       coalesce(try_cast('0.' || split_part(split_part(cleaned, ':', 2), '.', 2) AS DOUBLE), 0.0)
            ) / 60.0

          ELSE NULL
        END
      FROM (SELECT regexp_replace(trim(CAST(t AS VARCHAR)), '\\s+', '') AS cleaned)
    )
  END
);
"""


def _sql_quote(value: str) -> str:
    return value.replace("'", "''")


def create_race_results_query(s3_uri: str) -> str:
    safe_s3_uri = _sql_quote(s3_uri)
    return f"""
CREATE OR REPLACE TABLE race_results AS
WITH src AS (
    SELECT
        *,

        -- Canonical string versions (trim + cast) so output is consistent
        trim(CAST(roxzone_time AS VARCHAR)) AS roxzone_time_str,

        trim(CAST(run_1 AS VARCHAR)) AS run1_time_str,
        trim(CAST(run_2 AS VARCHAR)) AS run2_time_str,
        trim(CAST(run_3 AS VARCHAR)) AS run3_time_str,
        trim(CAST(run_4 AS VARCHAR)) AS run4_time_str,
        trim(CAST(run_5 AS VARCHAR)) AS run5_time_str,
        trim(CAST(run_6 AS VARCHAR)) AS run6_time_str,
        trim(CAST(run_7 AS VARCHAR)) AS run7_time_str,
        trim(CAST(run_8 AS VARCHAR)) AS run8_time_str,

        trim(CAST(run_time   AS VARCHAR)) AS run_time_str,
        trim(CAST(total_time AS VARCHAR)) AS total_time_str,

        trim(CAST(work_1 AS VARCHAR)) AS skiErg_time_str,
        trim(CAST(work_2 AS VARCHAR)) AS sledPush_time_str,
        trim(CAST(work_3 AS VARCHAR)) AS sledPull_time_str,
        trim(CAST(work_4 AS VARCHAR)) AS burpeeBroadJump_time_str,
        trim(CAST(work_5 AS VARCHAR)) AS rowErg_time_str,
        trim(CAST(work_6 AS VARCHAR)) AS farmersCarry_time_str,
        trim(CAST(work_7 AS VARCHAR)) AS sandbagLunges_time_str,
        trim(CAST(work_8 AS VARCHAR)) AS wallBalls_time_str,

        trim(CAST(work_time AS VARCHAR)) AS work_time_str

      FROM read_parquet(
          '{safe_s3_uri}',
          hive_partitioning=true,
          union_by_name=true,
          binary_as_string=true
      )
      WHERE try_cast(season AS INTEGER) IN (7, 8)
)
SELECT
    -- deterministic row id for linking
    md5(
        coalesce(event_id, '') || '|' ||
        coalesce(trim(name), '') || '|' ||
        coalesce(division, '') || '|' ||
        coalesce(total_time_str, '') || '|' ||
        coalesce(season, '') || '|' ||
        coalesce(location, '') || '|' ||
        coalesce(year, '')
    ) AS result_id,

    try_cast(season AS INTEGER) AS season,
    lower(location) AS location,
    try_cast(year AS INTEGER) AS year,

    age_group,
    division,
    event_id,
    event_name,
    gender,

    -- keep raw + cleaned name
    trim(name) AS name_raw,
    trim(name) AS name,

    trim(CAST(nationality AS VARCHAR)) AS nationality,

    -- ===== time strings =====
    roxzone_time_str AS roxzone_time,

    run1_time_str AS run1_time,
    run2_time_str AS run2_time,
    run3_time_str AS run3_time,
    run4_time_str AS run4_time,
    run5_time_str AS run5_time,
    run6_time_str AS run6_time,
    run7_time_str AS run7_time,
    run8_time_str AS run8_time,

    run_time_str   AS run_time,
    total_time_str AS total_time,

    skiErg_time_str            AS skiErg_time,
    sledPush_time_str          AS sledPush_time,
    sledPull_time_str          AS sledPull_time,
    burpeeBroadJump_time_str   AS burpeeBroadJump_time,
    rowErg_time_str            AS rowErg_time,
    farmersCarry_time_str      AS farmersCarry_time,
    sandbagLunges_time_str     AS sandbagLunges_time,
    wallBalls_time_str         AS wallBalls_time,

    work_time_str AS work_time,

    -- ===== seconds versions =====
    time_to_min(roxzone_time) AS roxzone_time_min,

    time_to_min(run1_time_str) AS run1_time_min,
    time_to_min(run2_time_str) AS run2_time_min,
    time_to_min(run3_time_str) AS run3_time_min,
    time_to_min(run4_time_str) AS run4_time_min,
    time_to_min(run5_time_str) AS run5_time_min,
    time_to_min(run6_time_str) AS run6_time_min,
    time_to_min(run7_time_str) AS run7_time_min,
    time_to_min(run8_time_str) AS run8_time_min,

    time_to_min(run_time_str)   AS run_time_min,
    time_to_min(total_time_str) AS total_time_min,

    time_to_min(skiErg_time_str)          AS skiErg_time_min,
    time_to_min(sledPush_time_str)        AS sledPush_time_min,
    time_to_min(sledPull_time_str)        AS sledPull_time_min,
    time_to_min(burpeeBroadJump_time_str) AS burpeeBroadJump_time_min,
    time_to_min(rowErg_time_str)          AS rowErg_time_min,
    time_to_min(farmersCarry_time_str)    AS farmersCarry_time_min,
    time_to_min(sandbagLunges_time_str)   AS sandbagLunges_time_min,
    time_to_min(wallBalls_time_str)       AS wallBalls_time_min,

    time_to_min(work_time_str) AS work_time_min

FROM src
WHERE
    try_cast(year AS INTEGER) IS NOT NULL
    AND lower(location) NOT IN ('season-8', 'none', '');

"""


DEFAULT_S3_URI = "s3://hyrox-results/processed/parquet/season=*/location=*/year=*/*.parquet"
CREATE_RACE_RESULTS = create_race_results_query(DEFAULT_S3_URI)

# Reporting: race_rankings
# Goal: pre-compute race/season/overall standings for fast percentile lookups.
# What: ranks every result by total_time_min across key cohorts.
# Why: UI needs instant "relative to competition" metrics without recomputing windows.
# Note: event_* fields are location-level cohorts to handle multi-day event IDs.
CREATE_RACE_RANKINGS = """
CREATE OR REPLACE TABLE race_rankings AS
WITH base AS (
    SELECT
        result_id,
        event_id,
        season,
        location,
        year,
        division,
        gender,
        age_group,
        total_time_min
    FROM race_results
    WHERE total_time_min IS NOT NULL
)
SELECT
    *,
    row_number() OVER (
        PARTITION BY location, division, gender, age_group
        ORDER BY total_time_min
    ) AS event_rank,
    count(*) OVER (
        PARTITION BY location, division, gender, age_group
    ) AS event_size,
    1.0 - percent_rank() OVER (
        PARTITION BY location, division, gender, age_group
        ORDER BY total_time_min
    ) AS event_percentile,
    row_number() OVER (
        PARTITION BY season, division, gender, age_group
        ORDER BY total_time_min
    ) AS season_rank,
    count(*) OVER (
        PARTITION BY season, division, gender, age_group
    ) AS season_size,
    1.0 - percent_rank() OVER (
        PARTITION BY season, division, gender, age_group
        ORDER BY total_time_min
    ) AS season_percentile,
    row_number() OVER (
        PARTITION BY division, gender, age_group
        ORDER BY total_time_min
    ) AS overall_rank,
    count(*) OVER (
        PARTITION BY division, gender, age_group
    ) AS overall_size,
    1.0 - percent_rank() OVER (
        PARTITION BY division, gender, age_group
        ORDER BY total_time_min
    ) AS overall_percentile
FROM base;
"""

# Reporting: split_percentiles
# Goal: provide per-split percentile performance inside a race cohort.
# What: unpivots split columns into rows and ranks each split by location cohort.
# Why: enables UI to highlight strengths/weaknesses per run/station segment.
# Note: split_* fields are location-level cohorts to handle multi-day event IDs.
CREATE_SPLIT_PERCENTILES = """
CREATE OR REPLACE TABLE split_percentiles AS
WITH base AS (
    SELECT
        result_id,
        event_id,
        season,
        location,
        year,
        division,
        gender,
        age_group,
        'run_1' AS split_name,
        run1_time_min AS split_time_min
    FROM race_results
    WHERE run1_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'run_2', run2_time_min
    FROM race_results
    WHERE run2_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'run_3', run3_time_min
    FROM race_results
    WHERE run3_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'run_4', run4_time_min
    FROM race_results
    WHERE run4_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'run_5', run5_time_min
    FROM race_results
    WHERE run5_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'run_6', run6_time_min
    FROM race_results
    WHERE run6_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'run_7', run7_time_min
    FROM race_results
    WHERE run7_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'run_8', run8_time_min
    FROM race_results
    WHERE run8_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'ski_erg', skiErg_time_min
    FROM race_results
    WHERE skiErg_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'sled_push', sledPush_time_min
    FROM race_results
    WHERE sledPush_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'sled_pull', sledPull_time_min
    FROM race_results
    WHERE sledPull_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'burpee_broad_jump', burpeeBroadJump_time_min
    FROM race_results
    WHERE burpeeBroadJump_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'row_erg', rowErg_time_min
    FROM race_results
    WHERE rowErg_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'farmers_carry', farmersCarry_time_min
    FROM race_results
    WHERE farmersCarry_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'sandbag_lunges', sandbagLunges_time_min
    FROM race_results
    WHERE sandbagLunges_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'wall_balls', wallBalls_time_min
    FROM race_results
    WHERE wallBalls_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'roxzone', roxzone_time_min
    FROM race_results
    WHERE roxzone_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'run_total', run_time_min
    FROM race_results
    WHERE run_time_min IS NOT NULL
    UNION ALL
    SELECT result_id, event_id, season, location, year, division, gender, age_group,
        'work_total', work_time_min
    FROM race_results
    WHERE work_time_min IS NOT NULL
)
SELECT
    *,
    row_number() OVER (
        PARTITION BY location, division, gender, age_group, split_name
        ORDER BY split_time_min
    ) AS split_rank,
    count(*) OVER (
        PARTITION BY location, division, gender, age_group, split_name
    ) AS split_size,
    1.0 - percent_rank() OVER (
        PARTITION BY location, division, gender, age_group, split_name
        ORDER BY split_time_min
    ) AS split_percentile
FROM base;
"""

# Reporting: athlete_history
# Goal: provide a per-athlete race history enriched with percentile standings.
# What: joins athlete_results to race_results and race_rankings.
# Why: allows UI to fetch a full report without composing multiple joins.
CREATE_ATHLETE_HISTORY = """
CREATE OR REPLACE TABLE athlete_history AS
SELECT
    ar.athlete_id,
    r.result_id,
    r.event_id,
    r.season,
    r.location,
    r.year,
    r.division,
    r.gender,
    r.age_group,
    r.name,
    r.total_time_min,
    rr.event_rank,
    rr.event_size,
    rr.event_percentile,
    rr.season_rank,
    rr.season_size,
    rr.season_percentile,
    rr.overall_rank,
    rr.overall_size,
    rr.overall_percentile
FROM athlete_results ar
JOIN race_results r ON r.result_id = ar.result_id
LEFT JOIN race_rankings rr ON rr.result_id = r.result_id;
"""
