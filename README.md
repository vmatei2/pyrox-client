# pyrox-client

Unofficial Python client for HYROX race results.

![Unit Tests](https://github.com/vmatei2/pyrox-client/actions/workflows/tests.yml/badge.svg)
![Integration Tests](https://github.com/vmatei2/pyrox-client/actions/workflows/integration.yml/badge.svg)
[![Docs](https://img.shields.io/badge/docs-mkdocs-0b5d4a)](https://vmatei2.github.io/pyrox-client/)
[![PyPI - Version](https://img.shields.io/pypi/v/pyrox-client.svg)](https://pypi.org/project/pyrox-client/)
[![Wheel](https://img.shields.io/pypi/wheel/pyrox-client.svg)](https://pypi.org/project/pyrox-client/)

## Install

```bash
uv pip install pyrox-client
```

or

```bash
pip install pyrox-client
```

## Quickstart

```python
import pyrox

client = pyrox.PyroxClient()

# Discover races
races = client.list_races()

# Fetch one race
london = client.get_race(season=7, location="london")

# Optional filters
london_male_open = client.get_race(
    season=7,
    location="london",
    gender="male",
    division="open",
)

# Total time filter in minutes
sub60 = client.get_race(season=7, location="london", total_time=60)
range_50_60 = client.get_race(season=7, location="london", total_time=(50, 60))

# Athlete lookup in a race
athlete = client.get_athlete_in_race(
    season=7,
    location="london",
    athlete_name="surname, name",
)
```

## Core API

- `list_races(season: int | None = None, force_refresh: bool = False) -> pd.DataFrame`
- `get_race(season, location, year=None, gender=None, division=None, total_time=None, use_cache=True) -> pd.DataFrame`
- `get_season(season, locations=None, gender=None, division=None, max_workers=8, use_cache=True) -> pd.DataFrame`
- `get_athlete_in_race(season, location, athlete_name, year=None, gender=None, division=None, use_cache=True) -> pd.DataFrame`
- `clear_cache(pattern="*") -> None`
- `cache_info() -> dict`

## Documentation

- Live docs: https://vmatei2.github.io/pyrox-client/
- Client API: `docs/api.md`
- Error model: `docs/errors.md`
- Filters and usage notes: `docs/filters.md`

## Repository Scope

The PyPI package is the `pyrox` client library.

This repository also contains a reporting service and UI (`pyrox_api_service/`, `ui/`) used for project workflows. Those are not part of the published `pyrox-client` wheel.

Maintainer-only operational docs:

- `docs/maintainers/README.md`
- `docs/maintainers/release.md`
- `docs/maintainers/reporting-service.md`

## Disclaimer

Pyrox is an independent project and is not affiliated with, endorsed, or sponsored by HYROX.
HYROX and related marks are trademarks of their respective owners and are used only for descriptive purposes.
