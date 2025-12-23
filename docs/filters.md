# Filtering

Pyrox supports high-signal filtering at read time, so you can load only the rows you need.

## Gender and division

These filters are applied server-side for efficiency.

```commandline
race = client.get_race(
    season=7,
    location="london",
    gender="male",      # "male" | "female" | "mixed"
    division="open",   # "open" | "pro"
)
```

Notes:
- Values are case-sensitive in the underlying parquet filter; prefer lowercase.
- If the filtered dataset has no rows, Pyrox raises `RaceNotFound`.

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
