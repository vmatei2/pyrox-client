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

## [2026-07-24] sync | Self-contained architecture-wiki skill + freshness hook

Added `/codewiki`: `.claude/skills/codewiki/{SKILL.md,analyze.py,lint.py}` plus
a SessionStart hook `.claude/hooks/codewiki-freshness.py`.

Took CodeWiki's *approach* (static analysis before prose, leaf-first ordering,
module-level incremental invalidation) without its runtime. Evaluated its MCP
server first and dropped it: 6 of its 8 tools are Read/Write/JSON in a
trenchcoat, and the 7th (`get_prompt`) is a handful of templates. Only
`analyze_repo` had real content, and `ast` + import regex reproduces it for a
repo this size — 48 files, 12.6k LOC, 217 components, 78 in-repo edges, ~2s.
Recursive decomposition dropped entirely: it exists to fit repos that don't fit
in context, and this one does.

`analyze.py finalize` validates the module tree against the index before
writing the baseline, so a hallucinated component ID fails loudly rather than
silently mis-scoping future drift checks — upstream accepts whatever the model
emits. `lint.py` replaces the Node-subprocess Mermaid validation with a
zero-dependency syntax lint (unquoted labels, unbalanced subgraph/end, banned
directives) plus cross-link checking.

On-disk contract (`metadata.json`, `module_tree.json`) is kept byte-compatible
with CodeWiki's, so the hook is agnostic and upstream could still be run over
the same directory. The baseline commit is the one the *analysis* saw, not HEAD
at write time — otherwise commits made mid-run vanish from the next diff.

The dangling Stop-hook entry for the removed `wiki-drift-guard.sh` was dropped
from `.claude/settings.json`. Background: `docs/research/codewiki-analysis.md`.

## [2026-07-24] sync | MCP division schema

Added `relay` and `adaptive` to the MCP `Division` enum. The reporting API has
always accepted data-backed division values, but the MCP schema was a stale
four-value literal, so clients could neither present nor validate the two
supported cohorts. A schema-level regression test now protects the public tool
contract.
## [2026-07-24] sync | First codewiki_docs/ generation; JS import-regex bug fixed

Generated the seven-module wiki into `codewiki_docs/` (2,600 lines of module
docs plus an overview) and finalized the drift baseline at `5156d889`. Modules:
python_client, service_runtime, reporting_engine, mcp_surface, ui_shell,
ui_modes, ui_data_and_charts. Boundaries came from the import graph, not the
folder tree — which is why `reporting_engine` (2,522 LOC of cohort math) is
split out of the `pyrox_api_service` package it physically lives in.

Fixed a real bug in `analyze.py` found by one of the writing agents: the JS
import regex could not cross newlines, so every multi-line
`import {\n a,\n b,\n} from './x'` block — the dominant style in this UI —
was invisible. 78 -> 87 edges, none lost. Understated fan-in for
`formatters.js` (10 -> 13), `segments.js` (4 -> 7), `UiPrimitives.jsx` (6 -> 7)
and hid `DeepdiveMode -> api/client.js` entirely. Module boundaries were
unaffected; all nine recovered edges are UI-internal.

Generation surfaced findings worth triaging into active-work.md if confirmed:
`/api/health` returns the DuckDB path unauthenticated; no DuckDB connection
reuse anywhere (corroborating the known slowness investigation); profile
percentiles cost ~110 full-table queries for a ten-race athlete; sync MCP tool
functions block the event loop; `SeasonProgressionChart.jsx` and
`AppLoadingScreen.jsx` are dead code with live CSS; heavy copy-paste across the
six page modes. These are generated claims — unverified by tests, so confirm
before acting.
