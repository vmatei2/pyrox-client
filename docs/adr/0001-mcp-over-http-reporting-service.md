# Expose Pyrox to LLMs via an MCP server over the HTTP reporting service

## Context

We want Claude (and later Codex) to answer natural-language questions against the
HYROX dataset ("what's the distribution of men's results?"). The `ReportingClient`
already offers a raw `query(sql)` escape hatch and `plot_cohort_distribution()`
against the local 817MB DuckDB file, which is the most flexible path.

## Decision

The MCP server wraps the **hosted FastAPI reporting service over HTTP**, exposing a
small set of **intent-shaped tools** rather than the raw `ReportingClient`. The MCP
endpoint is mounted on the existing `pyrox_api_service` ASGI app and deployed to the
same Fly app; users connect by adding one URL as a remote connector. Aggregates
(distributions, percentiles) are **computed server-side** — including a new thin
`/api/distribution` endpoint — and tools return **structured data only**, leaving
chart rendering to the model's own code tool.

## Considered Options

- **Wrap `ReportingClient` / expose `query(sql)` directly.** Rejected: raw SQL over a
  public connector is an injection / runaway-query / cost surface, requires hosting the
  817MB DB with the MCP layer, and pushes cohort-definition and analysis correctness
  into ad-hoc model-generated code (non-deterministic, easy to get subtly wrong).
- **Let the model compute aggregates from raw rows.** Rejected: re-introduces the
  raw-data-dump cost and makes cohort/normalization logic non-reproducible.

## Consequences

- The cohort definition lives in exactly one place (server), so distributions and
  percentiles are deterministic and reproducible across runs and clients.
- New question types that the curated endpoints don't cover require a backend change
  (a new endpoint), not just a prompt tweak — a deliberate trade of flexibility for
  correctness and safety.
- Clients without a code/analysis tool receive data but no rendered chart.
