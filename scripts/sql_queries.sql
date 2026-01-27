-- file used to simply testing queries directly onto the db inside vscode using the db explorer

-- Race rankings input rows (this is the base CTE in CREATE_RACE_RANKINGS)
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
WHERE total_time_min IS NOT NULL;

-- Event-level cohort for a specific result_id (location/division/gender/age_group)
-- Replace :result_id with a real value.
WITH picked AS (
  SELECT location, division, gender, age_group
  FROM race_results
  WHERE result_id = :result_id
)
SELECT
  r.result_id,
  r.name,
  r.total_time_min,
  row_number() OVER (
    PARTITION BY r.location, r.division, r.gender, r.age_group
    ORDER BY r.total_time_min
  ) AS event_rank,
  count(*) OVER (
    PARTITION BY r.location, r.division, r.gender, r.age_group
  ) AS event_size,
  1.0 - percent_rank() OVER (
    PARTITION BY r.location, r.division, r.gender, r.age_group
    ORDER BY r.total_time_min
  ) AS event_percentile
FROM race_results r
JOIN picked p
  ON r.location IS NOT DISTINCT FROM p.location
 AND r.division IS NOT DISTINCT FROM p.division
 AND r.gender IS NOT DISTINCT FROM p.gender
 AND r.age_group IS NOT DISTINCT FROM p.age_group
WHERE r.total_time_min IS NOT NULL
ORDER BY r.total_time_min;

-- Season-level cohort for a specific result_id (season/division/gender/age_group)
WITH picked AS (
  SELECT season, division, gender, age_group
  FROM race_results
  WHERE result_id = :result_id
)
SELECT
  r.result_id,
  r.name,
  r.total_time_min,
  row_number() OVER (
    PARTITION BY r.season, r.division, r.gender, r.age_group
    ORDER BY r.total_time_min
  ) AS season_rank,
  count(*) OVER (
    PARTITION BY r.season, r.division, r.gender, r.age_group
  ) AS season_size,
  1.0 - percent_rank() OVER (
    PARTITION BY r.season, r.division, r.gender, r.age_group
    ORDER BY r.total_time_min
  ) AS season_percentile
FROM race_results r
JOIN picked p
  ON r.season IS NOT DISTINCT FROM p.season
 AND r.division IS NOT DISTINCT FROM p.division
 AND r.gender IS NOT DISTINCT FROM p.gender
 AND r.age_group IS NOT DISTINCT FROM p.age_group
WHERE r.total_time_min IS NOT NULL
ORDER BY r.total_time_min;

-- Overall cohort for a specific result_id (division/gender/age_group)
WITH picked AS (
  SELECT division, gender, age_group
  FROM race_results
  WHERE result_id = :result_id
)
SELECT
  r.result_id,
  r.name,
  r.total_time_min,
  row_number() OVER (
    PARTITION BY r.division, r.gender, r.age_group
    ORDER BY r.total_time_min
  ) AS overall_rank,
  count(*) OVER (
    PARTITION BY r.division, r.gender, r.age_group
  ) AS overall_size,
  1.0 - percent_rank() OVER (
    PARTITION BY r.division, r.gender, r.age_group
    ORDER BY r.total_time_min
  ) AS overall_percentile
FROM race_results r
JOIN picked p
  ON r.division IS NOT DISTINCT FROM p.division
 AND r.gender IS NOT DISTINCT FROM p.gender
 AND r.age_group IS NOT DISTINCT FROM p.age_group
WHERE r.total_time_min IS NOT NULL
ORDER BY r.total_time_min;
