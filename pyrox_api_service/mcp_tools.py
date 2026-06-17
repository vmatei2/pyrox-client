"""Intent-shaped tool logic for the Pyrox MCP server.

These are plain functions that call the FastAPI reporting service in-process
(via an httpx ASGI transport, so no network socket is opened) and shape the
result for an LLM caller. Transport and tool registration live in mcp_app.py.

Keeping the logic here as ordinary functions means it can be unit-tested without
standing up an MCP session.
"""

from __future__ import annotations

from typing import Optional

from starlette.testclient import TestClient

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
    gender: str,
    season: Optional[int] = None,
    division: Optional[str] = None,
    metric: str = "overall",
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
    gender: Optional[str] = None,
    division: Optional[str] = None,
) -> dict:
    """Resolve an athlete name to candidate races (each carries a `result_id`).

    Use this first when a user names an athlete: pick a `result_id` from
    `matches`, then call get_race_report / get_deepdive with it.
    """
    payload = _get(
        "/api/athletes/search",
        {"name": name, "gender": gender, "division": division},
    )
    if "error" in payload:
        return payload
    races = payload.get("races", [])
    return {
        "total": payload.get("count", len(races)),
        "returned": min(len(races), limit),
        "matches": races[:limit],
    }


def get_rankings(
    season: int,
    division: str,
    gender: str,
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
    division: Optional[str] = None,
    gender: Optional[str] = None,
    age_group: Optional[str] = None,
    location: Optional[str] = None,
    metric: str = "total_time_min",
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
    division: Optional[str] = None,
) -> dict:
    """Career profile for an athlete, by `athlete_id` (preferred) or `name`."""
    if athlete_id:
        return _get(f"/api/athletes/{athlete_id}/profile", {"division": division})
    if name:
        return _get("/api/athletes/profile", {"name": name, "division": division})
    return {"error": "Provide either athlete_id or name.", "status_code": 400}


def list_filters(
    season: Optional[int] = None,
    division: Optional[str] = None,
    gender: Optional[str] = None,
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
    gender: Optional[str] = None,
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
    gender: Optional[str] = None,
    division: Optional[str] = None,
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
