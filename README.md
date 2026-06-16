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

DuckDB-backed reporting helpers are optional. The extra installs the DuckDB
Python library, but it does not bundle a database file:

```bash
pip install "pyrox-client[reporting]"
```

## Quickstart

```python
import pyrox

client = pyrox.PyroxClient()

# Discover races
races = client.list_races()
seasons = client.list_seasons()
locations = client.list_locations(season=8)
years = client.list_years(season=8, location="london")

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
- `list_seasons(force_refresh: bool = False) -> list[int]`
- `list_locations(season: int | None = None, force_refresh: bool = False) -> list[str]`
- `list_years(season: int | None = None, location: str | None = None, force_refresh: bool = False) -> list[int]`
- `get_race(season, location, year=None, gender=None, division=None, total_time=None, use_cache=True) -> pd.DataFrame`
- `get_season(season, locations=None, gender=None, division=None, max_workers=8, use_cache=True) -> pd.DataFrame`
- `get_athlete_in_race(season, location, athlete_name, year=None, gender=None, division=None, use_cache=True) -> pd.DataFrame`
- `clear_cache(pattern="*") -> None`
- `cache_info() -> dict`

## Mistake Recovery

`RaceNotFound` includes manifest-backed suggestions when a race cannot be found:

```python
from pyrox.errors import RaceNotFound

try:
    client.get_race(season=8, location="londn")
except RaceNotFound as exc:
    print(exc)
    print(exc.suggestions)
```

## Reporting Helpers

The base install keeps the public client lightweight. `ReportingClient` requires
`pyrox-client[reporting]` and a local DuckDB database path; the package does not
ship the generated database artifact.

```python
from pyrox.reporting import ReportingClient

reporting = ReportingClient(database="/path/to/pyrox_duckdb")
```

## MCP Server

The hosted reporting service exposes a read-only MCP server over streamable HTTP at
`https://pyrox-api.fly.dev/mcp/`. It lets Claude answer natural-language questions
against the HYROX dataset through a small set of intent-shaped tools:
`list_filters`, `find_athlete`, `get_distribution`, `get_rankings`,
`get_race_report`, `get_deepdive`, and `get_athlete_profile`.

Add it to Claude Code with the `claude mcp add` command:

```bash
claude mcp add --transport http pyrox https://pyrox-api.fly.dev/mcp/
```

Then verify the connection:

```bash
claude mcp list
```

By default this registers the server at the local (project) scope. Use
`--scope user` to make it available across all your projects:

```bash
claude mcp add --transport http --scope user pyrox https://pyrox-api.fly.dev/mcp/
```

To remove it:

```bash
claude mcp remove pyrox
```

For example prompts, tool semantics, and caveats, see `docs/mcp.md`.

## Documentation

- Live docs: https://vmatei2.github.io/pyrox-client/
- Client API: `docs/api.md`
- MCP guide: `docs/mcp.md`
- Error model: `docs/errors.md`
- Filters and usage notes: `docs/filters.md`

## Repository Scope

The PyPI package is the `pyrox` client library.

This repository also contains a reporting service and UI (`pyrox_api_service/`, `ui/`) used for project workflows. Those are not part of the published `pyrox-client` wheel.

Reporting-service contract note:

- Athlete profile endpoints (`/api/athletes/profile` and `/api/athletes/{athlete_id}/profile`)
  may include optional `personal_bests[*].percentile` values in `[0, 1]`.
- `average_times[*].percentile` may also be present with the same semantics.
- Missing percentile data is non-fatal and returned by omitting the `percentile` key
  for that segment.
- Profile percentile cohorts are computed against historical results in the same
  division and gender.

Maintainer-only operational docs:

- `docs/maintainers/README.md`
- `docs/maintainers/release.md`
- `docs/maintainers/reporting-service.md`

## Disclaimer

Pyrox is an independent project and is not affiliated with, endorsed, or sponsored by HYROX.
HYROX and related marks are trademarks of their respective owners and are used only for descriptive purposes.
