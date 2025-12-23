# Quickstart

## Install

Using uv:

```commandline
uv pip install -e .
```

Or from PyPI:

```commandline
uv pip install pyrox-client
```

## Create a client

```commandline
import pyrox

client = pyrox.PyroxClient()
```

## Discover races

```commandline
races = client.list_races(season=7)
print(races.head())
```

## Load a single race

```commandline
london = client.get_race(
    season=7,
    location="london",
    gender="male",
    division="open",
)
```

## Load a season (parallelized)

```commandline
season7 = client.get_season(season=7, locations=["london", "barcelona"])
```

## Pull a specific athlete

```commandline
athlete = client.get_athlete_in_race(
    season=7,
    location="london",
    athlete_name="surname, name",
)
```

## Next

- See Filtering for precise time-window queries.
- See Data Model to understand columns and types.
- See Analytics and Reproducible Research for notes of race-analysis workflows.
