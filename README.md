# pyrox-client

Talk to the HYROX results dataset. A Python client and a public MCP server for
analysing HYROX race results, either in code or by asking an AI assistant.

![Unit Tests](https://github.com/vmatei2/pyrox-client/actions/workflows/tests.yml/badge.svg)
![Integration Tests](https://github.com/vmatei2/pyrox-client/actions/workflows/integration.yml/badge.svg)
[![Docs](https://img.shields.io/badge/docs-mkdocs-0b5d4a)](https://vmatei2.github.io/pyrox-client/)
[![PyPI - Version](https://img.shields.io/pypi/v/pyrox-client.svg)](https://pypi.org/project/pyrox-client/)

<!-- Demo: one HYROX question typed into Claude, one chart out. MP4 autoplays on GitHub. -->

https://github.com/user-attachments/assets/2756c10f-166b-45ba-aa3d-089e1f40fe00




Two ways in:

- **Ask an AI.** Connect the MCP server and query the dataset in plain English,
  e.g. *"where would a 62-minute open time rank in season 8?"*
- **Write Python.** Pull a full race as a pandas DataFrame with splits already
  converted to minutes, cached on disk so reruns are cheap.

> Independent project, not affiliated with or endorsed by HYROX.

## Ask an AI (MCP server)

There's a public, read-only MCP server at `https://pyrox-api.fly.dev/mcp/`. Point
Claude, Codex, or any MCP client at it and ask about distributions, rankings,
athlete profiles, or a split-by-split race report. The assistant picks the right
tool for the question on its own.

```bash
# Claude Code
claude mcp add --transport http pyrox https://pyrox-api.fly.dev/mcp/

# Codex
codex mcp add pyrox --url https://pyrox-api.fly.dev/mcp/
```

Using Claude web or Desktop? No install needed; add it as a custom connector.
The [MCP guide](docs/mcp.md) has the steps, the full tool list, and example
prompts. If you connect a Strava MCP alongside it, you can ask the agent to check
your splits against the effort your Strava data actually shows.

## Use it in Python

```bash
pip install pyrox-client
```

```python
import pyrox

client = pyrox.PyroxClient()

london = client.get_race(season=7, location="london", gender="male")
print(london["total_time"].describe())

# Find what's available first
client.list_seasons()
client.list_locations(season=8)
```

Station and run columns come back with readable names, already in minutes, so you
can drop them straight into a stats workflow. See [docs/api.md](docs/api.md) for
the full reference.

## Core API

- `list_races(season=None)`, `list_seasons()`, `list_locations(...)`, `list_years(...)`
- `get_race(season, location, year=None, gender=None, division=None, total_time=None)`
- `get_season(season, locations=None, gender=None, division=None)`
- `get_athlete_in_race(season, location, athlete_name, ...)`
- `clear_cache(pattern="*")`, `cache_info()`

Mistype a location and `RaceNotFound` hands back the closest matches instead of a
bare error.

## Reporting helpers (optional)

For heavier local analysis over a DuckDB file, install the extra:

```bash
pip install "pyrox-client[reporting]"
```

The database artifact isn't bundled; you point `ReportingClient` at a local path.
Details in [docs/api.md](docs/api.md).

## Documentation

- Live docs: https://vmatei2.github.io/pyrox-client/
- MCP guide, client API, filters, and the error model live under `docs/`
- Background write-up: [Pyrox MCP server on Medium](https://medium.com/@vladmatei432/pyrox-mcp-server-access-to-and-analysis-of-hyrox-results-directly-via-llms-4e8ebf486525)

Maintaining or releasing? See [docs/maintainers/](docs/maintainers/README.md).

## License

MIT. Free to use, modify, and distribute. © 2026 Vlad Matei.
