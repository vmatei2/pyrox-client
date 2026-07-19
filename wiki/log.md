# Wiki log

Append-only record of wiki activity, newest entry last. Entry format:
`## [YYYY-MM-DD] <type> | <title>` where type ∈ ingest | sync | query | lint | seed.
List recent entries with: `grep "^## \[" wiki/log.md | tail -5`

## [2026-07-19] seed | Initial wiki creation

Replaced the never-run OpenWiki setup (scheduled external regeneration) with
this agent-maintained wiki. Read the full codebase (`src/pyrox`,
`pyrox_api_service`, `ui/`, docs, ADR, maintainer runbooks, recent git history)
and seeded 13 pages. Synthesis captured: race-report slowness fix (`a9cd559`)
is in but unverified against production; MCP DNS-rebinding protection is off
deliberately; wheel-content discipline is enforced by
`scripts/verify_wheel_contents.py`.

## [2026-07-19] lint | Consolidated 13 pages to 6

The initial seed was too big for a ~7k LOC repo. Merged quickstart,
architecture, source-map, operations, and testing into overview.md; merged the
four component pages into components.md. domain-concepts and active-work kept.
Same content density, less than half the maintenance surface. CLAUDE.md wiki
rules shortened to match, and the /wiki skill trimmed to the lint checklist
only (sync instructions live solely in CLAUDE.md now).
