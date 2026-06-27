"""Intent-shaped tool logic for the Pyrox MCP server.

These are plain functions that call the FastAPI reporting service in-process
(via an httpx ASGI transport, so no network socket is opened) and shape the
result for an LLM caller. Transport and tool registration live in mcp_app.py.

Keeping the logic here as ordinary functions means it can be unit-tested without
standing up an MCP session.
"""

from __future__ import annotations

from typing import Literal, Optional

from starlette.testclient import TestClient

# Stable, closed-vocabulary parameters are typed as Literals so their valid
# values land in each tool's input schema. The model then picks from the enum
# instead of guessing strings the service would reject, and usually skips a
# list_filters round-trip. age_group and location are intentionally left as
# free strings: they drift across seasons/events, so a frozen list here would
# go stale and reject valid new values. Use list_filters to discover those.
Gender = Literal["male", "female", "mixed"]
Division = Literal["open", "pro", "doubles", "pro_doubles"]

# Distribution accepts friendly segment keys (normalized to lowercase-alnum and
# looked up in _DISTRIBUTION_METRIC_COLUMN_MAP).
DistributionMetric = Literal[
    "overall",
    "run1",
    "run2",
    "run3",
    "run4",
    "run5",
    "run6",
    "run7",
    "run8",
    "skierg",
    "sledpush",
    "sledpull",
    "burpeebroadjump",
    "rowerg",
    "farmerscarry",
    "sandbaglunges",
    "wallballs",
]

# Deepdive resolves against the canonical time columns (its default is already
# a column name), so it carries the run/work/roxzone aggregates distribution
# does not expose.
DeepdiveMetric = Literal[
    "total_time_min",
    "run_time_min",
    "work_time_min",
    "roxzone_time_min",
    "run1_time_min",
    "run2_time_min",
    "run3_time_min",
    "run4_time_min",
    "run5_time_min",
    "run6_time_min",
    "run7_time_min",
    "run8_time_min",
    "skiErg_time_min",
    "sledPush_time_min",
    "sledPull_time_min",
    "burpeeBroadJump_time_min",
    "rowErg_time_min",
    "farmersCarry_time_min",
    "sandbagLunges_time_min",
    "wallBalls_time_min",
]

try:  # Prefer installed package import.
    from pyrox_api_service import app as api
except ModuleNotFoundError:  # pragma: no cover - direct repo execution fallback
    import app as api  # type: ignore

# Default page size for list-returning tools. Kept small so we don't dump large
# row sets into the model's context; callers raise `limit` to drill in.
DEFAULT_LIST_LIMIT = 20

# Synchronous in-process ASGI client. This drives the real FastAPI request path
# (validation, Query defaults, error mapping) without opening a network socket.
_client = TestClient(api.app)


def _get(path: str, params: Optional[dict] = None) -> dict:
    """Call a service endpoint in-process; return JSON, or an error dict on failure."""
    clean = {k: v for k, v in (params or {}).items() if v is not None}
    resp = _client.get(path, params=clean)
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        return {"error": detail, "status_code": resp.status_code}
    return resp.json()


def get_distribution(
    gender: Gender,
    season: Optional[int] = None,
    division: Optional[Division] = None,
    metric: DistributionMetric = "overall",
    age_group: Optional[str] = None,
    location: Optional[str] = None,
) -> dict:
    """Cohort distribution (histogram bins + summary stats) for a metric.

    Defaults to the latest season and the `open` division when unspecified.
    Gender is required. Thin cohorts come back with `small_sample: true`.
    """
    return _get(
        "/api/distribution",
        {
            "gender": gender,
            "season": season,
            "division": division,
            "metric": metric,
            "age_group": age_group,
            "location": location,
        },
    )


def find_athlete(
    name: str,
    limit: int = DEFAULT_LIST_LIMIT,
    gender: Optional[Gender] = None,
    division: Optional[Division] = None,
    match: str = "best",
    nationality: Optional[str] = None,
    require_unique: bool = False,
) -> dict:
    """Resolve an athlete name to candidate races (each carries a `result_id`).

    Use this first when a user names an athlete: pick a `result_id` from
    `matches`, then call get_race_report / get_deepdive with it. Ambiguous
    names return candidate races by default; set `require_unique=true` to force
    strict disambiguation.
    """
    payload = _get(
        "/api/athletes/search",
        {
            "name": name,
            "gender": gender,
            "division": division,
            "match": match,
            "nationality": nationality,
            "require_unique": require_unique,
            "limit": limit,
        },
    )
    if "error" in payload:
        return payload
    races = payload.get("races", [])
    return {
        "total": payload.get("total", payload.get("count", len(races))),
        "returned": len(races),
        "matches": races,
    }


def get_rankings(
    season: int,
    division: Division,
    gender: Gender,
    age_group: Optional[str] = None,
    athlete_name: Optional[str] = None,
    limit: int = DEFAULT_LIST_LIMIT,
    target_time_min: Optional[float] = None,
) -> dict:
    """Leaderboard for a season+division+gender cohort.

    Returns the full cohort `count` plus the fastest `limit` rows; raise `limit`
    to see more. `target_time_min` reports where a hypothetical time would place.
    """
    return _get(
        "/api/rankings",
        {
            "season": season,
            "division": division,
            "gender": gender,
            "age_group": age_group,
            "athlete_name": athlete_name,
            "limit": limit,
            "target_time_min": target_time_min,
        },
    )


def get_race_report(result_id: str, split_name: Optional[str] = None) -> dict:
    """Full split-by-split report for one race result (from a `result_id`).

    Get the `result_id` from find_athlete first.
    """
    return _get(f"/api/reports/{result_id}", {"split_name": split_name})


def get_deepdive(
    result_id: str,
    season: int,
    division: Optional[Division] = None,
    gender: Optional[Gender] = None,
    age_group: Optional[str] = None,
    location: Optional[str] = None,
    metric: DeepdiveMetric = "total_time_min",
) -> dict:
    """Cross-location cohort deep dive for one race result (from a `result_id`)."""
    return _get(
        f"/api/deepdive/{result_id}",
        {
            "season": season,
            "division": division,
            "gender": gender,
            "age_group": age_group,
            "location": location,
            "metric": metric,
        },
    )


def get_athlete_profile(
    name: Optional[str] = None,
    athlete_id: Optional[str] = None,
    division: Optional[Division] = None,
) -> dict:
    """Career profile for an athlete, by `athlete_id` (preferred) or `name`."""
    if athlete_id:
        return _get(f"/api/athletes/{athlete_id}/profile", {"division": division})
    if name:
        return _get("/api/athletes/profile", {"name": name, "division": division})
    return {"error": "Provide either athlete_id or name.", "status_code": 400}


def list_filters(
    season: Optional[int] = None,
    division: Optional[Division] = None,
    gender: Optional[Gender] = None,
) -> dict:
    """Valid filter values (seasons, divisions, genders, locations, age groups).

    Call this to discover what cohorts exist before querying distributions or rankings.
    """
    return _get(
        "/api/filter-options",
        {"season": season, "division": division, "gender": gender},
    )


def list_races(
    season: Optional[int] = None,
    gender: Optional[Gender] = None,
) -> dict:
    """Available races with participant counts, optionally filtered by season or gender.

    Returns distinct races showing event name, location, season, year, and
    how many athletes participated. Use this to discover which races exist
    before requesting a race summary.
    """
    return _get(
        "/api/races",
        {"season": season, "gender": gender},
    )


def get_race_summary(
    season: int,
    location: str,
    gender: Optional[Gender] = None,
    division: Optional[Division] = None,
    age_group: Optional[str] = None,
    top_percentile: Optional[float] = None,
) -> dict:
    """Summary statistics across all timing segments for a specific race.

    Returns count, min, max, mean, median, p10, p90 for every timing
    segment (total, each run, each station, aggregate run/work/roxzone).

    Use `list_races` first to discover valid season + location pairs.
    Set `top_percentile` (e.g. 10) to restrict to the fastest N percent of
    finishers and see what their segment times look like.
    """
    return _get(
        "/api/race-summary",
        {
            "season": season,
            "location": location,
            "gender": gender,
            "division": division,
            "age_group": age_group,
            "top_percentile": top_percentile,
        },
    )


def get_cohort_segment_averages(
    season: int,
    location: str,
    gender: Optional[Gender] = None,
    division: Optional[Division] = None,
    age_group: Optional[str] = None,
    top_n: Optional[int] = None,
    bottom_n: Optional[int] = None,
) -> dict:
    """Per-segment statistics for a rank-based slice of athletes in one race.

    Athletes are ranked by total time. Set `top_n` for the fastest N
    athletes, `bottom_n` for the slowest N, or omit both for all athletes.
    The two are mutually exclusive.

    Response separates `runs` (Run 1-8) and `stations` (SkiErg through
    Wall Balls) so you can compare pacing across segments. Includes
    `group_averages` with the mean across all run and station segment means.

    Use `list_races` first to discover valid season + location pairs.
    Call multiple times with different slices (e.g. top_n=20, bottom_n=20,
    and no slice) to compare cohorts.
    """
    return _get(
        "/api/cohort-segment-averages",
        {
            "season": season,
            "location": location,
            "gender": gender,
            "division": division,
            "age_group": age_group,
            "top_n": top_n,
            "bottom_n": bottom_n,
        },
    )
