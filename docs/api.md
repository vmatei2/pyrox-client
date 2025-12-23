# Client API

## `PyroxClient`

Create a client:

```commandline
from pyrox import PyroxClient
client = PyroxClient()
```

### `list_races(season: int | None = None, force_refresh: bool = False)`

Return a DataFrame of available races. Filter by season when provided.

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
