# FAQ

## Which seasons are covered?

Seasons 1 to 9, spanning 2018 to 2026: 316 races across 134 locations as of the
July 2026 data publish. Coverage grows weekly, so check `client.list_seasons()`
for the current picture, and see [the dataset](dataset.md) for a full breakdown.

## Why are times in minutes?

Times are normalized on load so your analysis can use numeric operations directly.

## How do I update cached data?

Pass `force_refresh=True` to `list_races` or `use_cache=False` to any read method.

## Why does a race return empty?

If a filter removes every row, `RaceNotFound` is raised. Try removing filters to
confirm the base dataset exists.
