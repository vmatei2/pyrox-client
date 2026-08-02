# Client API

## `PyroxClient`

Create a client:

```commandline
from pyrox import PyroxClient
client = PyroxClient()
```

### `list_races(season: int | None = None, force_refresh: bool = False)`

Return a DataFrame of available race editions. Each edition is identified by
the `season`, `location`, and `year` columns, so a city that appears in two
calendar years within one season is returned twice.

```python
client.list_races(season=7).query("location == 'paris'")
```

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
- With `year`, returns that specific calendar-year edition.
- Without `year`, combines every matching edition for the location and season.

!!! note "Race editions from 0.2.7"

    A HYROX season can span two calendar years. Use
    `get_race(season=7, location="paris", year=2025)` when you need one
    edition. Omitting `year` intentionally returns both Paris 2024 and Paris
    2025 in one DataFrame.

The supported division vocabulary is `open`, `pro`, `doubles`, `pro_doubles`,
`relay` and `adaptive`. Which of them show up depends on what the race actually
ran, so check `df["division"].unique()` rather than assuming.

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

Parallelized race fetching with a configurable worker pool. Every available
`(location, year)` edition is fetched once, including locations that occur in
both calendar years of the season.

### `clear_cache(pattern: str = "*")`

Clear cached items matching a glob pattern.

### `cache_info() -> dict`

Return cache statistics and keys.

## Reporting Service Note (Repository-Only)

This repository also ships a FastAPI reporting service (`pyrox_api_service/`) that
is separate from the published `pyrox-client` wheel.

The optional `pyrox-client[reporting]` extra installs the DuckDB Python library
needed by `ReportingClient`, but it does not bundle a DuckDB database file. Use
`ReportingClient(database="/path/to/pyrox_duckdb")` when you have a local
generated database artifact.

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
