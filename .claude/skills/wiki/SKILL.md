---
name: wiki
description: Health-check the agent-maintained wiki in wiki/ (lint). Use when the user says "wiki lint", "check the wiki", or periodically after a stretch of changes. Day-to-day sync rules live in CLAUDE.md, not here.
---

# Wiki lint

Sync-after-change is defined in CLAUDE.md. This checklist is the periodic
health check. Fix the mechanical findings (dead links, stale dates) directly;
report the structural ones before rewriting anything.

1. Staleness: compare each page's `updated:` against
   `git log -1 --format=%cs -- <path>` for every path in its `sources:` list.
   A page older than its sources is suspect, not automatically wrong; verify
   before rewriting.
2. Dead links: every relative link in `wiki/*.md` must resolve, including the
   repo paths named in `sources:`.
3. Orphans: pages missing from `wiki/index.md`.
4. Coverage: significant new directories or modules no `sources:` list claims.
5. Contradictions: claims that disagree across pages, or with `docs/`,
   `AGENTS.md`, or the code itself.
6. active-work.md: confirm listed items are still open; check git history for
   evidence something was finished.

Finish by appending `## [YYYY-MM-DD] lint | <summary>` to `wiki/log.md` with
what was found and fixed.
