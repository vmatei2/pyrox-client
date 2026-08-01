---
template: home.html
title: HYROX data for analysts, coaches and athletes
description: >-
  HYROX race results as data: a Python client that returns full races as pandas
  DataFrames, plus a public MCP server your AI assistant can query.
hide:
  - navigation
  - toc
---

## Two ways into HYROX results data

Pyrox is the data layer, not another leaderboard site, so pick whichever route
fits how you already work.

<div class="pyrox-split" markdown>
<div markdown>

### Just ask your AI assistant

Point any MCP client at the public endpoint and ask in plain English. There's no
sign-up and no key to paste, and you never write SQL: the assistant picks the
right tool and the analytics run server-side.

```text
https://pyrox-api.fly.dev/mcp/
```

=== "Claude Code"

    ```bash
    claude mcp add --transport http pyrox \
      https://pyrox-api.fly.dev/mcp/
    ```

=== "Codex"

    ```bash
    codex mcp add pyrox \
      --url https://pyrox-api.fly.dev/mcp/
    ```

=== "Claude web / Desktop"

    Settings → Connectors → **Add custom connector**, then paste the URL
    above. No OAuth step; it connects straight away.

[Connect it in 60 seconds →](mcp.md)

</div>
<div markdown>

### Or get HYROX results in three lines of Python

A whole race as a `pandas.DataFrame`, splits already parsed into minutes and
columns already named. The first call downloads; everything after that reads
your local cache.

```python
import pyrox

client = pyrox.PyroxClient()
london = client.get_race(season=7, location="london")
london["total_time"].describe()
```

[Read the quickstart →](quickstart.md)

</div>
</div>

## Three questions it answers

Click one to see the actual call behind it.

<div class="pyrox-queries" markdown>

<details class="pyrox-query" markdown>
<summary>Where would a 62-minute open time rank overall in season 8?</summary>

```python
# MCP tool call — this is what an AI assistant runs on your behalf
get_rankings(season=8, division="open", gender="male", target_time_min=62)
```

</details>

<details class="pyrox-query" markdown>
<summary>How does my sled push compare with everyone who finished within a minute of me?</summary>

```python
import pyrox

client = pyrox.PyroxClient()
race = client.get_race(season=7, location="london", gender="male", division="open")
me = client.get_athlete_in_race(
    season=7, location="london", athlete_name="surname, name"
).iloc[0]

nearby = race[(race["total_time"] - me["total_time"]).abs() <= 1]
nearby["sledPush_time"].describe()
```

</details>

<details class="pyrox-query" markdown>
<summary>What's the time distribution of burpee broad jumps for women pro athletes, with optional time-filtering?</summary>

```python
import pyrox

client = pyrox.PyroxClient()
season8 = client.get_season(season=8, gender="female", division="pro")
season8["burpeeBroadJump_time"].describe()

# optional: only sub-70-minute finishers
season8[season8["total_time"] < 70]["burpeeBroadJump_time"].describe()
```

</details>

</div>

## What you get back

<div class="pyrox-cards" markdown>
<div class="pyrox-card" markdown>

### Every segment, not just the finish

Each run and station comes back as its own column, along with roxzone
transition time, where plenty of races are actually lost.

</div>
<div class="pyrox-card" markdown>

### Already in minutes

Nothing to parse out of `HH:MM:SS`: times arrive as numeric minutes in
canonical columns, so they drop straight into pandas, DuckDB or a model.

</div>
<div class="pyrox-card" markdown>

### Real divisions

`open`, `pro`, `doubles`, `pro_doubles`, `relay` and `adaptive` stay separate by
default, because pooling them produces meaningless averages.

</div>
<div class="pyrox-card" markdown>

### Cohorts, stated honestly

Rankings and distributions name the cohort they used and flag thin samples,
rather than reporting a percentile from a handful of finishers as if it meant
something.

</div>
<div class="pyrox-card" markdown>

### Cached and reproducible

Races are cached locally on first pull, so notebooks re-run cheaply and give the
same answer tomorrow.

</div>
<div class="pyrox-card" markdown>

### Helpful when you're wrong

Mistype a location and `RaceNotFound` hands back the closest matches rather than
a bare stack trace.

</div>
</div>

## Ten tools, one endpoint

The MCP server exposes intent-shaped tools rather than raw SQL, so an assistant
can go from a vague question to a defensible answer without inventing the maths.

| Tool | Use it for |
| --- | --- |
| `list_filters` | Discover available seasons, divisions, genders, locations and age groups. |
| `list_races` | Find valid season and location pairs. |
| `find_athlete` | Resolve a name to candidate results. |
| `get_race_report` | One athlete's full race, split by split. |
| `get_athlete_profile` | Historical results and personal bests. |
| `get_distribution` | Histogram bins and summary stats for a cohort. |
| `get_race_summary` | Timing stats for every segment in one race. |
| `get_cohort_segment_averages` | Run and station averages for all, top-N or bottom-N finishers. |
| `get_rankings` | Leaderboard rows and hypothetical target-time placement. |
| `get_deepdive` | One result against cross-location cohorts for a metric. |

The server is read-only and idempotent. It computes analytics; it doesn't expose
arbitrary SQL or bulk row exports.

[See every tool, with example prompts →](mcp.md)

## Don't write another HYROX scraper

The idea behind Pyrox is simple: make HYROX results easy to get at, so you can
go straight to running the numbers. Pyrox handles the scraping and delivery —
races land as Parquet on a CDN, cached locally when you pull them.

## Pair it with your training data

Connect a Strava MCP alongside Pyrox and one assistant can see both your race
splits and the training that led into them, so your own numbers get read against
the whole field rather than on their own.

## Common questions

??? question "Is there an official HYROX API?"

    Not a public, documented one. HYROX publishes results through a timing
    portal built for looking up one athlete at a time, with no bulk export and
    no developer API, which is why Pyrox exists.

??? question "Do I need an API key?"

    No. Both the MCP server and the REST API are open and read-only. They're
    rate-limited to keep the load sane, but nothing asks you to sign up, paste
    a key or go through OAuth.

??? question "Is Pyrox affiliated with HYROX?"

    No. It's an independent open-source project built on publicly available
    results, and it is not affiliated with or endorsed by HYROX.

??? question "Which seasons, divisions and locations are covered?"

    Coverage tracks the upstream dataset and grows over time, so the question
    is best put to the data itself: call `list_filters` from an AI assistant,
    or `client.list_seasons()` and `client.list_locations()` in Python.
    Divisions are `open`, `pro`, `doubles`, `pro_doubles`, `relay` and
    `adaptive`.

??? question "Can Claude or ChatGPT query HYROX results?"

    Yes; that's what the MCP server is for. Any MCP-capable client (Claude
    Code, Claude web and Desktop, Codex, and others) can connect to
    `https://pyrox-api.fly.dev/mcp/` and query the dataset in plain English.

??? question "Can I use this commercially?"

    The `pyrox-client` code is MIT licensed, so you can use, modify and
    redistribute it freely, including commercially. The underlying race
    results are public HYROX data; Pyrox claims no ownership of it, and what
    you may do with that data is yours to check independently.

??? question "What if I spot a data issue?"

    Open an issue on the [pyrox-client GitHub repo](https://github.com/vmatei2/pyrox-client/issues).
    We read every one and try to fix real problems quickly.

<div class="pyrox-note" markdown>
**Independent project.** Pyrox is not affiliated with or endorsed by HYROX. It's
built on public HYROX results and may inherit issues present in the source data.
MIT licensed, so you're free to use, modify and distribute it.
</div>
