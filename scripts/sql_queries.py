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

CREATE_RACE_RESULTS = f"""
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
        's3://hyrox-results/processed/parquet/season=8/location=*/year=*/*.parquet',
        hive_partitioning=true,
        union_by_name=true
    )
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

    nationality,

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
