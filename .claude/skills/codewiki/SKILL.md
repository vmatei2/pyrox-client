---
name: codewiki
description: Generate or refresh the architecture wiki in codewiki_docs/, or check whether it has gone stale. Use when the user says "codewiki", "regenerate the architecture docs", "are the generated docs stale", or when the session-start freshness hook reports drift.
---

# Architecture wiki generation

Produces `codewiki_docs/` — a navigable architecture wiki for pyrox-client,
grounded in a real import graph. Adapted from CodeWiki
([paper](https://arxiv.org/abs/2510.24428), analysis in
`docs/research/codewiki-analysis.md`) but deliberately **flat**: CodeWiki's
recursive decomposition and sub-agent delegation exist to fit repos that don't
fit in a context window. This one is ~12.6k LOC across 48 files. Read it all,
cluster once, write once.

Two directories this must never touch:

- `wiki/` — the hand-curated agent knowledge base (`CLAUDE.md` owns its rules).
- `docs/` — the user-facing mkdocs site.

`codewiki_docs/` is disposable and regenerable; those two are not.

## What we kept from CodeWiki, and what we dropped

| Kept | Dropped |
|---|---|
| Static analysis before prose, so boundaries follow real dependencies | Tree-sitter (stdlib `ast` + import regex is enough at this size) |
| Leaf-first ordering: components before the overview that summarizes them | Recursive clustering, `max_depth`, token-budget delegation |
| Module-level incremental invalidation via `module_tree.json` | The MCP server, the CLI, `caw`, a second model subscription |
| Mermaid validation before a doc is accepted | Node/Chromium — `lint.py` is a syntax lint, not a renderer |

The on-disk contract (`metadata.json`, `module_tree.json`) is byte-compatible
with CodeWiki's, so `.claude/hooks/codewiki-freshness.py` works either way and
you could still run the upstream tool over the same directory.

## Mode selection

```bash
python3 .claude/hooks/codewiki-freshness.py --text
```

| Result | Do this |
|---|---|
| `absent`, `empty_tree`, `baseline_lost`, `unreadable` | Full generation |
| `stale` | Update the named modules only |
| fresh | Say so and stop. Do not regenerate |

## Full generation

### 1. Analyze

```bash
python3 .claude/skills/codewiki/analyze.py analyze
```

Runs in ~2s, writes `.codewiki/analysis.json` (gitignored) and prints a
clustering brief: files per top-level directory, dependency hubs by fan-in,
entry points nothing imports, and the largest files. The full index has every
component (`path::Symbol`, kind, line span, docstring) and every in-repo import
edge.

Treat the brief as the reading plan: hubs and large files first, since they
carry the architecture. JS/TS symbols are regex-derived and marked
`"approximate": true` — verify anything load-bearing by reading the file.

### 2. Cluster

Group components into **5–7 modules**, using the import graph rather than
directory names alone — the point of analyzing first is that folder layout and
architecture disagree. Judge by: who depends on whom (`edges`), what the entry
points are, and where a boundary would let a reader stop reading.

Write the tree to `.codewiki/tree.json`:

```json
{
  "module_name": {
    "components": ["pyrox_api_service/app.py::create_app"],
    "children": {}
  }
}
```

Component IDs must be copied byte-for-byte from the index; `finalize` rejects
invented ones. A bare file path is accepted where a whole file belongs to a
module. Leave `children` empty — the flat structure is the point. Every source
file should land in exactly one module; `finalize` reports the ones that don't.

### 3. Write

One `<module_name>.md` per module in `codewiki_docs/`, then `overview.md` last
so it can summarize what the module docs actually say. Read the real source for
every claim — the index tells you what exists, not what it does.

Per module doc:
- What it is and why it exists, in the first paragraph.
- At least one Mermaid diagram (`graph TD`/`graph LR`). Quote every label
  containing punctuation: `A["Client (caching)"]`. No `click`/`linkStyle`.
- Component responsibilities, keyed to real symbols.
- Cross-links as `[Module](module_name.md)`; link out to `docs/` rather than
  restating user-facing material.
- 150–400 lines. `overview.md`: 80–200, with an end-to-end diagram.

With five or more modules, dispatch one `general-purpose` subagent per module —
they are independent. Give each the module's component IDs, the import edges
that cross its boundary, and the rules above. Write `overview.md` yourself once
they return.

### 4. Validate and baseline

```bash
python3 .claude/skills/codewiki/lint.py                              # mermaid, links, structure
python3 .claude/skills/codewiki/analyze.py finalize .codewiki/tree.json
```

Fix every lint error before finalizing. `finalize` refuses to write the
baseline if a component ID is invented, a module has no `.md`, `overview.md` is
missing, or files fall outside every module; `--force` overrides but records
the warnings. It writes `module_tree.json` and `metadata.json` with the commit
the *analysis* saw — not HEAD at write time, so commits made mid-run stay
visible to the next incremental check.

**Finalize is what creates the drift baseline.** Skip it and the freshness hook
reports `absent` forever.

## Incremental update

1. Re-run `analyze.py analyze` — the graph may have changed shape.
2. The hook's `affected_modules` names what drifted. Touch only those docs, and
   re-read the changed source before editing.
3. Refresh `overview.md` if module responsibilities or boundaries moved, not
   for every internal edit.
4. If the change added a file that belongs in no existing module, update
   `.codewiki/tree.json` — `finalize` will otherwise flag it as uncovered.
5. `lint.py`, then `finalize` to re-baseline.

Granularity is module-level and matching is substring-based, so expect
occasional over-invalidation. Updating a flagged module is cheaper than
arguing with the mapping.

## Guardrails

- Never write outside `codewiki_docs/` and `.codewiki/`. If generation shows
  the curated `wiki/` is wrong, report it — the `CLAUDE.md` wiki flow handles
  that separately.
- Generated prose is unverified: no test executes against it. It is a map, not
  a contract. Say so where a claim is inferred rather than read.
- Commit `codewiki_docs/`; `metadata.json` and `module_tree.json` are the
  shared drift baseline and are useless on one machine only.
- `.codewiki/` is scratch and gitignored.
