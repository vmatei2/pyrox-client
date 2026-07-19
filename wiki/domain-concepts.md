---
updated: 2026-07-19
sources:
  - docs/data-model.md
  - docs/duckdb-stabilization.md
  - pyrox_api_service/mcp_tools.py
---

# Domain concepts: HYROX vocabulary

HYROX is a fitness race: 8 × 1 km runs alternating with 8 workout stations in
fixed order. That structure explains most column names and cohort logic in the
codebase.

| Order | Station | Column stem |
|---|---|---|
| 1 | SkiErg (1000 m) | `skiErg_time` |
| 2 | Sled Push | `sledPush_time` |
| 3 | Sled Pull | `sledPull_time` |
| 4 | Burpee Broad Jumps | `burpeeBroadJump_time` |
| 5 | RowErg (1000 m) | `rowErg_time` |
| 6 | Farmers Carry | `farmersCarry_time` |
| 7 | Sandbag Lunges | `sandbagLunges_time` |
| 8 | Wall Balls | `wallBalls_time` |

Runs are `run1_time` through `run8_time`. Aggregates: `total_time`, `work_time`
(stations), `run_time` (runs), and `roxzone_time`, the transition zone between
run and station where an athlete is neither running nor working. Upstream data
stores times as `MM:SS` or `H:MM:SS` strings; both the client library and the
DuckDB artifact normalize to float minutes (`*_time_min` columns in DuckDB).

## Cohort dimensions

A **season** is a HYROX season number (season 8 is roughly 2025/26) spanning
many events worldwide, while **location** is a lowercased host-city slug like
`london-olympia` that can recur across calendar years. **gender** is `male`,
`female`, or `mixed` (doubles teams). **division** is `open`, `pro`, `doubles`,
or `pro_doubles`; pro means heavier weights, doubles share the work.
**age_group** values are free-form strings that drift across seasons, so never
hard-code them.

Two ids matter. **result_id** is a deterministic md5 key for one race entry;
`find_athlete` returns them and race reports and deep dives take them.
**athlete_id** is career-level identity, used by athlete profiles.

## Product vocabulary

A **race report** breaks one result down split-by-split against a comparison
cohort (same season, division, gender, optionally a time window). A
**deepdive** compares one result across locations within a season. **planner**
returns segment distributions for a hypothetical target cohort, **rankings** is
the leaderboard (with `target_time_min` placing an imaginary time), and a
**distribution** is histogram plus stats for one metric, flagged
`small_sample: true` under n=30.

## Data invariants (schema contract v1)

From `docs/duckdb-stabilization.md`: `race_results` guarantees non-null
`result_id`, `season`, `location`, `year`, `event_id`, `name`. Everything else
is nullable, so code defensively. DuckDB tables: `race_results`,
`race_rankings`, `athletes`, `athlete_results`, `athlete_index`,
`athlete_history`, `split_percentiles`, `build_info`.
