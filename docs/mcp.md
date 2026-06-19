# Try Pyrox MCP

Pyrox exposes a public, read-only MCP server at:

```text
https://pyrox-api.fly.dev/mcp/
```

Use it when you want Claude to answer natural-language questions about HYROX Race
Results without downloading the DuckDB artifact or writing Python. The connector
uses curated server-computed analytics: it does not expose raw SQL, arbitrary row
exports, or write operations.

## Add It To Claude Code

Register the connector:

```bash
claude mcp add --transport http pyrox https://pyrox-api.fly.dev/mcp/
```

Verify it is available:

```bash
claude mcp list
```

By default this registers the connector for the current project. To make it
available across your Claude Code projects:

```bash
claude mcp add --transport http --scope user pyrox https://pyrox-api.fly.dev/mcp/
```

Remove it later with:

```bash
claude mcp remove pyrox
```

## What It Can Answer

The MCP server exposes ten intent-shaped tools:

| Tool | Use it for |
| --- | --- |
| `list_filters` | Discover available seasons, divisions, genders, locations, and age groups. |
| `list_races` | Find valid season and location pairs before asking for race-level stats. |
| `find_athlete` | Resolve an athlete name to candidate Results with `result_id` values. |
| `get_race_report` | Inspect one Result's full Race report and Segment breakdown. |
| `get_athlete_profile` | Summarize an athlete's historical Results and personal bests. |
| `get_distribution` | Get a Cohort Distribution as histogram bins and summary stats. |
| `get_race_summary` | Get timing stats for all Segments in one Race. |
| `get_cohort_segment_averages` | Compare Run and Station averages for all, top-N, or bottom-N athletes in one Race. |
| `get_rankings` | Query leaderboard rows and hypothetical target-time placement. |
| `get_deepdive` | Compare one Result against cross-location Cohorts for a metric. |

## Example Prompts

Start by discovering the available filters:

```text
Using Pyrox, what seasons, divisions, genders, and locations are available?
```

Find an athlete and inspect one Result:

```text
Using Pyrox, find results for James Ingham. Pick the most recent open Result and
summarize the Race report, including strongest and weakest Segments.
```

Compare a target finish time:

```text
Using Pyrox, where would a 62-minute male open time rank in season 8?
```

Ask for a Cohort Distribution:

```text
Using Pyrox, show the Distribution of female open finish times in season 8.
State the Cohort, sample size, and whether the sample is thin.
```

Build a profile:

```text
Using Pyrox, create an athlete profile for James Ingham and explain how his
Segment strengths compare with his historical Results.
```

## How To Read The Answers

Pyrox uses these terms consistently:

- **Race**: one HYROX event instance, identified by season, location, and year.
- **Result**: one athlete's performance in one Race.
- **Segment**: one timed Run or Station.
- **Roxzone**: transition time between Segments.
- **Cohort**: the reference population used for rankings, Distributions, and Percentiles.
- **Distribution**: histogram bins plus summary stats for a metric across a Cohort.

When a user names an athlete, Claude usually needs to follow this flow:

```text
find_athlete -> choose a result_id -> get_race_report or get_deepdive
```

The `result_id` is an internal identifier. Users do not need to know it in advance.
For common or ambiguous names, `find_athlete` returns candidate races so Claude
can choose the right Result or ask for a narrower filter.

## Caveats

- Pyrox is based on public HYROX source data and may inherit source-data issues.
- Thin Cohorts are flagged with sample-size information and should be interpreted
  cautiously.
- Divisions are not pooled by default because open, pro, doubles, and relay Results
  are not directly comparable.
- Distributions default to the latest season and the `open` division when those
  filters are omitted.
- Claude renders any charts from returned structured data; the server does not
  return image files.
- The public MCP endpoint is open and read-only. It is rate-limited to protect
  availability.

## Maintainer Smoke Test

Maintainers can verify the live connector with:

```bash
PYROX_MCP_URL=https://pyrox-api.fly.dev/mcp/ uv run python scripts/smoke_mcp.py --json
```
