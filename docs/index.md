---
template: home.html
title: HYROX data for analysis and race comparison
description: >-
  Load published HYROX race results into pandas, or query rankings and race
  reports through the public Pyrox MCP server.
hide:
  - navigation
  - toc
---

## Choose how you want to query it

Pyrox has two public entry points. They read data prepared by the same upstream
pipeline, but they suit different kinds of work.

<div class="pyrox-split" markdown>
<div markdown>

### Ask through MCP

Connect Claude, Codex or another MCP client to the read-only endpoint. The
assistant chooses a typed Pyrox tool; the reporting service runs the query.

```text
https://pyrox-api.fly.dev/mcp/
```

[MCP setup and tool reference →](mcp.md)

</div>
<div markdown>

### Work in pandas

The Python client downloads race-level Parquet files and returns a
`pandas.DataFrame`. Each run, station and transition time arrives as numeric
minutes.

```python
import pyrox

client = pyrox.PyroxClient()
london = client.get_race(season=7, location="london")
```

[Install the Python client →](quickstart.md)

</div>
</div>

## One ranking question, without SQL

Ask an MCP client:

> Where would a 62-minute male open time rank in season 8?

The assistant calls:

```python
get_rankings(
    season=8,
    division="open",
    gender="male",
    target_time_min=62,
)
```

The response gives the cohort size, target placement and nearby leaderboard
rows. It also carries the filters used for the calculation, which matters when
two superficially similar questions use different age groups or divisions.

## What the files contain

<div class="pyrox-facts" markdown>

- **One row per result.** Singles entries represent one athlete; doubles rows
  represent a pair. Repeat racers appear more than once.

- **Runs and stations stay separate.** The eight run legs, eight stations,
  roxzone time and race totals have their own columns.

- **Times are numeric minutes.** There is no `HH:MM:SS` parsing in notebook
  code.

- **Divisions aren't pooled.** Open, pro, doubles, pro doubles, relay and
  adaptive results remain separate unless you combine them yourself.

</div>

See [the dataset](dataset.md) for the measured coverage, complete schema and
weekly publication schedule.

## Operational limits

The dataset comes from public HYROX results and can inherit mistakes from the
source. Coverage changes with each weekly publish, while a local cache only
avoids repeated downloads; it does not freeze a research snapshot. Export a
dated Parquet file when an analysis must reproduce the same figures later.

The hosted REST and MCP service allows 60 requests per minute per IP. It may
take a few minutes to answer after a quiet period because its Fly.io machine
stops when idle. Python users read Parquet from the CDN and don't share that
rate limit.

## Common questions

??? question "Is there an official HYROX API?"

    HYROX doesn't publish a documented developer API. Its timing portal works
    well for finding one athlete, but it has no bulk export; Pyrox supplies the
    missing programmatic access.

??? question "Do I need an API key?"

    No. The MCP and REST endpoints are public and read-only, and the Python
    client downloads public race files. None of them asks you to create an
    account.

??? question "Which seasons, divisions and locations are covered?"

    The published manifest changes weekly. Check [the dataset](dataset.md) for
    the latest measured totals, call `list_filters` through MCP, or use
    `client.list_seasons()` and `client.list_locations()` in Python.

??? question "Can I use Pyrox commercially?"

    The client code uses the MIT licence, including for commercial use. That
    licence doesn't cover the underlying race records; check your intended data
    use separately.

??? question "Is Pyrox affiliated with HYROX?"

    No. Vlad Matei maintains Pyrox as an independent open-source project. It
    isn't affiliated with or endorsed by HYROX.

??? question "What should I do if a result looks wrong?"

    Compare it with the public HYROX result first, then open a
    [GitHub issue](https://github.com/vmatei2/pyrox-client/issues) with the race,
    result and column that differs.
