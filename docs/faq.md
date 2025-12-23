# FAQ

## Which seasons are covered?

Historical coverage for seasons 2-7 (with season 5-6 being most used in analysis).

## Why are times in minutes?

Times are normalized on load so your analysis can use numeric operations directly.

## How do I update cached data?

Pass `force_refresh=True` to `list_races` or `use_cache=False` to any read method.

## Why does a race return empty?

If a filter removes every row, `RaceNotFound` is raised. Try removing filters to
confirm the base dataset exists.
