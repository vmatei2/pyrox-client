---
title: "HYROX MCP server: query race results with Claude or Codex"
description: >-
  Connect the free, read-only Pyrox MCP server and ask an MCP client about
  HYROX splits, rankings and distributions. No API key needed.
---

# Connect the Pyrox MCP server

The public endpoint is:

```text
https://pyrox-api.fly.dev/mcp/
```

It runs typed reporting tools over the HYROX dataset. Clients can't send raw
SQL, export arbitrary rows or write data. The service does the calculation and
returns structured fields for the assistant to explain or chart.

## Claude Code

Add Pyrox to the current project:

```bash
claude mcp add --transport http pyrox https://pyrox-api.fly.dev/mcp/
```

Check the connection:

```bash
claude mcp list
```

Use `--scope user` if you want the connection in every Claude Code project:

```bash
claude mcp add --transport http --scope user pyrox https://pyrox-api.fly.dev/mcp/
```

Remove it with `claude mcp remove pyrox`.

## Claude web and Desktop

Custom connectors require a paid Claude plan. A Team or Enterprise admin may
need to allow them first.

1. Open **Settings**, then **Connectors**.
2. Select **Add custom connector**.
3. Enter `Pyrox` as the name.
4. Paste `https://pyrox-api.fly.dev/mcp/`, including the trailing slash.
5. Add the connector. Pyrox doesn't use OAuth or ask for an API key.
6. Enable Pyrox from the chat composer before sending a question. Claude asks
   you to approve the first tool call.

## Codex

Register the same HTTP endpoint:

```bash
codex mcp add pyrox --url https://pyrox-api.fly.dev/mcp/
```

Run `/mcp` in the Codex TUI to inspect the connection. You can also add it to
`~/.codex/config.toml` yourself:

```toml
[mcp_servers.pyrox]
url = "https://pyrox-api.fly.dev/mcp/"
```

The CLI and IDE extension read the same Codex configuration.

## MCP tools

| Tool | Returns |
| --- | --- |
| `list_filters` | Available seasons, divisions, genders, locations and age groups. |
| `list_races` | Valid season and location pairs. |
| `find_athlete` | Candidate results for an athlete name, including `result_id`. |
| `get_race_report` | One result with every available run and station split. |
| `get_athlete_profile` | Historical results and personal-best fields. |
| `get_distribution` | Histogram bins and summary statistics for a cohort. |
| `get_race_summary` | Segment timing statistics for one race. |
| `get_cohort_segment_averages` | Run and station averages for a selected group of finishers. |
| `get_rankings` | Leaderboard rows or the placement of a hypothetical finish time. |
| `get_deepdive` | One result compared with cross-location cohorts for a chosen metric. |

## Questions to try

Start with the available data when you don't know the exact filters:

```text
Using Pyrox, which season 8 locations have male open results?
```

Find an athlete before asking for a race report:

```text
Using Pyrox, find results for Vlad Matei. Use the most recent open result and
report the two station splits furthest from his cohort median.
```

A target time doesn't need an athlete record:

```text
Using Pyrox, where would a 62-minute male open time rank in season 8? State the
cohort size and filters with the answer.
```

For a distribution, name the metric and cohort:

```text
Using Pyrox, return the distribution of female open finish times in season 8.
Include the sample size and histogram bins.
```

## Result IDs and ambiguous names

A `result_id` identifies one performance in one race. You don't need to know it
beforehand: `find_athlete` returns candidate records, and the assistant can pick
one or ask you to narrow the name, season or location.

Names come from registration data, including misspellings. Search results may
therefore contain several spellings for the same person; check the race history
before treating them as one athlete.

## Service limits

- The source data may contain wrong names, divisions or split times.
- Small cohorts carry sample-size warnings and need cautious interpretation.
- Omitted distribution filters default to the latest season and `open` division.
- The endpoint allows 60 requests per minute per IP and may need a few minutes
  to start after sitting idle.
- Chart images come from the MCP client. Pyrox returns structured data rather
  than image files.
