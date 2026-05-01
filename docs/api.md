# Client API

## `PyroxClient`

Create a client:

```commandline
from pyrox import PyroxClient
client = PyroxClient()
```

### `list_races(season: int | None = None, force_refresh: bool = False)`

Return a DataFrame of available races. Filter by season when provided.

### `list_seasons(force_refresh: bool = False)`

Return sorted season values available in the manifest.

### `list_locations(season: int | None = None, force_refresh: bool = False)`

Return sorted location values available in the manifest. When `season` is
provided, results are limited to that season. Returns an empty list if no
locations match.

### `list_years(...)`

```commandline
list_years(
    season: int | None = None,
    location: str | None = None,
    force_refresh: bool = False,
) -> list[int]
```

Return sorted calendar years available in the manifest. Location matching is
case-insensitive. Returns an empty list if no years match.

### `get_race(...)`

```commandline
get_race(
    season: int,
    location: str,
    year: int | None = None,
    gender: str | None = None,
    division: str | None = None,
    total_time: float | tuple[float | None, float | None] | None = None,
    use_cache: bool = True,
) -> pd.DataFrame
```

Key behaviors:
- Applies server-side gender and division filters when available.
- Converts time columns into minutes.
- Supports strict time windows using `total_time`.

Division values seen in the dataset include `open`, `pro`, and `pro_doubles`.

If the manifest lookup fails, `RaceNotFound` includes discovery context such as
available seasons, available years, and close location suggestions:

```commandline
from pyrox.errors import RaceNotFound

try:
    client.get_race(season=8, location="londn")
except RaceNotFound as exc:
    print(exc.suggestions)
```

### `get_athlete_in_race(...)`

```commandline
get_athlete_in_race(
    season: int,
    location: str,
    athlete_name: str,
    year: int | None = None,
    gender: str | None = None,
    division: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame
```

Case-insensitive search on the `name` column. Raises `AthleteNotFound` if no match.

### `get_season(...)`

```commandline
get_season(
    season: int,
    locations: Iterable[str] | None = None,
    gender: str | None = None,
    division: str | None = None,
    max_workers: int = 8,
    use_cache: bool = True,
) -> pd.DataFrame
```

Parallelized race fetching with a configurable worker pool.

### `clear_cache(pattern: str = "*")`

Clear cached items matching a glob pattern.

### `cache_info() -> dict`

Return cache statistics and keys.

## Reporting Service Note (Repository-Only)

This repository also ships a FastAPI reporting service (`pyrox_api_service/`) that
is separate from the published `pyrox-client` wheel.

For athlete profile endpoints:

- `GET /api/athletes/profile?name=<name>`
- `GET /api/athletes/{athlete_id}/profile`

`personal_bests` entries may include an optional `percentile` field (float in
`[0, 1]`) per segment key (`overall`, `runplusroxzone`, `skierg`, `sledpush`,
`sledpull`, `burpeebroadjump`, `rowerg`, `farmerscarry`, `sandbaglunges`,
`wallballs`).

`average_times` entries may also include optional `percentile` with the same
range and segment keys.

Percentile direction matches report split percentiles:
- `1.0` means faster than 100% of the cohort.
- `0.0` means slower than everyone in the cohort.
- If percentile cannot be computed for a segment, the key is omitted for that
  segment without failing the endpoint.

Profile percentiles are computed against historical results in the same division
and gender.
