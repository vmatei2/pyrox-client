# Caching

Pyrox caches results locally for speed and repeatability. Cache entries store the
DataFrame plus metadata and ETags when available.

## Defaults

- Cache dir: `~/.cache/pyrox`
- Manifest TTL: 2 hours
- Race TTL: 2 hours
- Season TTL: 1 hour

## Opt out per call

```commandline
race = client.get_race(season=7, location="london", use_cache=False)
```

## Clear cache

```commandline
client.clear_cache()
client.clear_cache(pattern="race_7_london*")
```

## Inspect cache

```commandline
info = client.cache_info()
print(info)
```

Fields include `cache_dir`, `total_items`, `total_size_mb`, and cached keys.
