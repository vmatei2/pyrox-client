# Filtering

Pyrox filters at read time, so you load only the rows you need.

## Gender and division

These filters are applied server-side for efficiency.

```commandline
race = client.get_race(
    season=7,
    location="london",
    gender="male",      # "male" | "female" | "mixed"
    division="open",
)
```

Supported divisions are `open`, `pro`, `doubles`, `pro_doubles`, `relay`,
`adaptive`, `elite` and `elite_doubles`.

Notes:
- Values are case-sensitive in the underlying parquet filter; prefer lowercase.
- If the filtered dataset has no rows, Pyrox raises `RaceNotFound`.

## Elite results

Use `division="elite"` for Elite singles or `division="elite_doubles"` for pairs.
They are separate from `pro` and `pro_doubles`; not every race offers them.

```python
elite = client.get_race(
    season=8,
    location="hamburg",
    year=2025,
    division="elite",  # "elite_doubles" for pairs
    use_cache=False,
)
```

Season 8 includes 461 Elite singles and doubles results across Hamburg (2025),
Melbourne (2025), Phoenix (2026), EMEA London Olympia (2026), APAC Championship
Brisbane (2026), Warsaw (2026), Stockholm (2026) and Washington DC (2026).
Use `client.list_races(season=8)` to find the location slugs and years.

Published fractional seconds are preserved when times are converted to numeric
minutes. Missing source splits remain missing. These filters work with
`pyrox-client` 0.2.7; no package upgrade is needed for the new data.
`use_cache=False` downloads fresh results instead of reusing a cached race.

## Total time windows

`total_time` is expressed in minutes. You can pass a single value or an open interval.

```commandline
# Under 60 minutes
sub_60 = client.get_race(season=7, location="london", total_time=60)

# Open interval: 50 < total_time < 60
mid_pack = client.get_race(season=7, location="london", total_time=(50, 60))

# Only lower bound
slow = client.get_race(season=7, location="london", total_time=(70, None))
```

Notes:
- Bounds are strict (`>` and `<`), not inclusive.
- Filtering happens after time columns are converted to minutes.
