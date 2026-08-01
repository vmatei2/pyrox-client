---
title: The HYROX results dataset
description: >-
  What's in the HYROX results dataset behind Pyrox: every run and station split,
  how it's structured, how often it updates, and how to query it.
---

# The HYROX results dataset

Pyrox publishes HYROX race results as structured, analysis-ready data. One row
is one entry (an athlete, or a pair in doubles divisions) in one race, with every
timed segment of that race as its own numeric column.

## Coverage

Measured from the published manifest on **30 July 2026**. Coverage grows every
week, so treat these as floor values rather than fixed totals.

| Dimension | Coverage |
| --- | --- |
| Race results | **1,235,605** rows |
| Races | **316** (season × location × year) |
| Locations | **134** |
| Seasons | **1–9**, spanning **2018–2026** |
| Genders | `male`, `female`, `mixed` |
| Format | Parquet on a CDN, ~105 MB compressed |

Per season, the dataset has grown sharply with the sport:

| Season | Races | Locations | Results |
| ---: | ---: | ---: | ---: |
| 1 | 9 | 9 | 4,750 |
| 2 | 11 | 11 | 7,271 |
| 3 | 4 | 4 | 1,433 |
| 4 | 24 | 21 | 15,538 |
| 5 | 38 | 34 | 43,607 |
| 6 | 53 | 49 | 144,114 |
| 7 | 69 | 65 | 289,842 |
| 8 | 104 | 97 | 698,163 |
| 9 | 4 | 4 | 30,887 |

!!! warning "Results, not athletes"

    1,235,605 counts **result rows**, not unique people. One athlete racing
    three times is three rows, and a doubles row represents a pair. Don't quote
    it as an athlete count.

## How to see current coverage

=== "Ask an AI"

    ```text
    Using Pyrox, what seasons, divisions, genders, locations and age groups
    are available?
    ```

=== "Python"

    ```python
    import pyrox

    client = pyrox.PyroxClient()
    client.list_seasons()
    client.list_locations(season=8)
    client.list_races(season=8)
    ```

=== "REST"

    ```bash
    curl https://pyrox-api.fly.dev/api/filter-options
    ```

## Schema

Each race arrives as a `pandas.DataFrame`. **All time columns are floats in
minutes**, parsed once on load, so there's no `HH:MM:SS` handling left in your
analysis code.

### Identity and totals

| Column | Type | Meaning |
| --- | --- | --- |
| `name` | string | Athlete name as shown on the official results site |
| `gender` | string | `male`, `female` or `mixed` |
| `division` | string | Division label, lowercase (see below) |
| `age_group` | string | Age bracket, e.g. `30-34` |
| `nationality` | string | Nationality as recorded upstream |
| `event_id` | string | Identifier for the race |
| `event_name` | string | Human-readable race name |
| `source_result_id` | string | Upstream identifier for the row |
| `total_time` | float (min) | Total race time |
| `work_time` | float (min) | Total time spent on stations |
| `run_time` | float (min) | Total running time across all eight legs |
| `roxzone_time` | float (min) | Total transition time between segments |

That's 12 columns; with the 16 segment columns below, 28 in total.

### The eight stations

| Column | Station |
| --- | --- |
| `skiErg_time` | SkiErg |
| `sledPush_time` | Sled push |
| `sledPull_time` | Sled pull |
| `burpeeBroadJump_time` | Burpee broad jumps |
| `rowErg_time` | RowErg |
| `farmersCarry_time` | Farmers carry |
| `sandbagLunges_time` | Sandbag lunges |
| `wallBalls_time` | Wall balls |

### The eight runs

`run1_time` through `run8_time`: each 1 km leg gets its own column, so you can
watch pacing decay across the race instead of staring at one aggregate running
number.

!!! note "Two surfaces, two schemas"

    The columns above describe the Parquet files the Python client reads. The
    hosted reporting service (REST and MCP) uses canonical `*_time_min` columns
    internally and resolves friendly metric aliases at its boundary. Don't
    assume a column name from one surface exists on the other; see
    [Data model](data-model.md) and the [Client API](api.md).

### Schema drift

Upstream data evolves between seasons. Check `df.columns` and adapt rather than
assuming a column is always present.

## Divisions

The supported division vocabulary is `open`, `pro`, `doubles`, `pro_doubles`,
`relay` and `adaptive`. Which of them appear in any given race depends on what
that event ran, so check with `list_filters` or by inspecting
`df["division"].unique()` rather than assuming all six are present.

Pyrox doesn't pool divisions by default: an open athlete and a pro athlete
aren't doing the same work, so a combined average benchmarks nothing and a
combined percentile misleads.

## How it is built and how often it updates

An upstream pipeline scrapes and compiles the race results, then publishes
immutable Parquet files and a DuckDB artifact to a CDN on a **weekly cadence**
(the scraper starts Tuesdays at 12:00 UTC; the artifact is typically live by
around 18:30 UTC). The hosted service picks up the new artifact on its next
boot, and a scheduled job at 20:00 UTC on Tuesdays restarts warm machines so
they refresh promptly.

Nothing gets installed unverified: the service checks the schema version and a
SHA-256 checksum, and refuses any artifact whose schema version is newer than
the one it supports. A bad or unexpected upstream publish therefore can't
silently change the answers you get.

The Python client caches whatever it downloads locally, so a notebook you ran
last month gives the same answer today unless you clear the cache.

## Three ways to query it

| Access path | Best for | Cost |
| --- | --- | --- |
| [Python client](quickstart.md) | Notebooks, modelling, bulk analysis | `pip install pyrox-client`, free |
| [MCP server](mcp.md) | Conversational analysis with Claude, Codex or another MCP client | Public endpoint, no key |
| REST API | Dashboards and applications | Public endpoint, rate-limited |

The Python client reads Parquet from the CDN directly and has no rate limit,
which makes it the right choice for bulk work. The hosted service is limited to
**60 requests per minute per IP**, shared across REST and MCP calls, and returns
`429` past that. The service also scales to zero when idle, so the first request
after a quiet period can take a few minutes to answer while it boots and
verifies the current database artifact.

## Licence and attribution

The `pyrox-client` code is MIT licensed: use, modify and redistribute it freely,
including commercially.

The underlying results are public HYROX data. Pyrox claims no ownership of it
and is not affiliated with or endorsed by HYROX. A link back to this project is
appreciated if you publish analysis built on the dataset, though not required;
what you may do with the underlying race data is yours to check independently.

Pyrox is built on public source data and may inherit issues present in it.
Where a cohort is small, the reporting surfaces say so rather than quietly
reporting a percentile from a handful of finishers.
