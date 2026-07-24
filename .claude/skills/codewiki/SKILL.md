---
name: codewiki
description: Generate, refresh, or review the single engineering architecture map at codewiki_docs/overview.md. Use when the user says "codewiki", asks to update or review the architecture overview, or when a change affects architecture, ownership, a durable contract, cross-component flow, deployment, runtime, or operator workflow.
---

# Architecture overview

Maintain exactly one generated engineering document:
`codewiki_docs/overview.md`. It is a high-signal map for both humans and
agents, not a complete restatement of the source.

## Workflow

1. Read the current overview, `AGENTS.md`, relevant `docs/`, and the real
   architecture-bearing source. Use `rg --files`, imports, entry points, and
   deployment configuration to navigate. Verify every durable claim in code.
2. Update only `codewiki_docs/overview.md`. Keep it roughly 120–250 lines and
   include:
   - the system purpose and source-of-truth note;
   - one clear end-to-end Mermaid diagram;
   - deliverables, data/request paths, and component ownership;
   - stable domain/API contracts and important operational constraints;
   - a "change this here" map and the essential test/deploy commands.
3. Link to detailed `docs/` or source files instead of copying them. Mark
   inference as inference. Do not record temporary worktree state, active
   investigations, exhaustive symbol lists, or findings that belong in an
   issue.
4. Validate:

   ```bash
   python3 .claude/skills/codewiki/lint.py --strict
   ```

Never create additional files in `codewiki_docs/`, and never edit `docs/` as a
side effect of generation. If code and the overview disagree, code wins.
