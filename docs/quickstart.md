# Quickstart

## Install from PyPI

With uv:

```bash
uv pip install pyrox-client
```

Plain pip works too:

```bash
pip install pyrox-client
```

To edit the client itself, clone the repository and run `uv pip install -e .`
inside its virtual environment.

## Find an available race

```python
import pyrox

client = pyrox.PyroxClient()
races = client.list_races(season=7)
print(races.head())
```

`list_races()` reads the published manifest, so use it rather than guessing a
location slug or year. Smaller helpers return plain Python lists:

```python
seasons = client.list_seasons()
locations = client.list_locations(season=8)
years = client.list_years(season=8, location="london")
```

## Load a race

```python
london = client.get_race(
    season=7,
    location="london",
    gender="male",
    division="open",
)

print(london.shape)
print(london[["name", "division", "total_time"]].head())
```

The return value is a `pandas.DataFrame`. Time columns use numeric minutes, and
station names appear as columns such as `sledPush_time` and `wallBalls_time`.
The first call downloads the race file; later calls can reuse the local cache.

## Load several races

`get_season()` downloads races concurrently. Pass `locations` when you only
need a subset:

```python
season7 = client.get_season(
    season=7,
    locations=["london", "barcelona"],
    division="open",
)
```

## Find one athlete

```python
athlete = client.get_athlete_in_race(
    season=7,
    location="london",
    athlete_name="surname, name",
)
```

The name match ignores case. It can still return several rows, so inspect the
result before selecting one.

## Where to go next

[Filtering](filters.md) explains strict time windows and division filters.
[Data model](data-model.md) lists the common columns, while [Analytics](analytics.md)
contains notebook-sized calculations. For cache expiry and refresh controls,
read [Caching](caching.md).
