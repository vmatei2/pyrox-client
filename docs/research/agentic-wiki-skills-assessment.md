# Agentic wiki and skills assessment

Reviewed: 2026-07-24

## Verdict

The design is state of the art in **shape**, but overbuilt in **volume** for
Pyrox today.

The good shape is: short root instructions, repository-local knowledge,
on-demand skills, deterministic checks, and generated architecture material
kept subordinate to code and curated documentation. That is the same
progressive-disclosure pattern described by Anthropic, OpenAI, and GitHub.

The overbuilt part is the second, generated documentation system. For a
12.6k-LOC/48-file repository, Pyrox now carries 2,739 lines of generated
architecture prose plus 1,267 lines of generator, lint, and freshness
machinery. The curated `wiki/` is only 415 lines and already provides the
high-value map, decisions, gotchas, and active work. The generated layer is
useful as an experiment and as a deep-reading aid, but it is not yet earning
its roughly 4,000-line maintenance surface as an always-present repository
contract.

**Recommendation:** keep the curated wiki and its small lint skill. Keep
`CLAUDE.md`/`AGENTS.md` as short routers. Put `codewiki_docs/` into on-demand
mode: retain the analyzer and `/codewiki` workflow, but do not make freshness a
session-start obligation. Prefer a compact generated overview plus selected
deep dives (`reporting_engine` and `mcp_surface`) over seven 300–400-line
module chapters. Reconsider full generation when the repository is large
enough that direct source retrieval repeatedly fails, roughly an order of
magnitude from its current size.

## What current strong systems actually do

These are directly supported observations from primary sources.

- **Anthropic:** `CLAUDE.md` is always loaded, so it should contain only
  broadly applicable, non-inferable context. Anthropic explicitly says to
  exclude file-by-file descriptions, frequently changing facts, detailed API
  docs, and long tutorials; use skills for occasional workflows and hooks only
  for actions that must happen every time. It also recommends treating
  instructions like code: prune and test them when behavior goes wrong.
  [Claude Code best practices](https://code.claude.com/docs/en/best-practices)
  and [memory guidance](https://code.claude.com/docs/en/memory).

- **OpenAI:** its agent-first case study reports that a large `AGENTS.md`
  crowded out task context, became noisy, rotted, and was hard to verify. The
  replacement is a roughly 100-line map into a structured, versioned
  documentation system of record, with progressive disclosure, CI linters,
  and a recurring doc-gardening agent.
  [Harness engineering](https://openai.com/index/harness-engineering/).
  Current Codex also layers root-to-leaf `AGENTS.md` files and caps their
  combined default load at 32 KiB; its skills load full instructions only when
  selected.
  [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
  and [Codex skills](https://learn.chatgpt.com/docs/build-skills).

- **GitHub Copilot:** persistent instructions are for broadly applicable
  conventions; path-specific instructions avoid overloading the root, and
  skills provide just-in-time procedures. GitHub explicitly says to use a
  skill instead when guidance is workflow-specific or large enough to
  distract from the task.
  [CLI customization comparison](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/comparing-cli-features)
  and [response customization](https://docs.github.com/en/copilot/concepts/prompting/response-customization).
  Its newer repository memory stores small facts with citations to supporting
  code, revalidates those citations against the current branch before use, and
  expires unused facts after 28 days. That is a useful direction of travel:
  retrieve and validate the smallest relevant fact, rather than trust a bulk
  snapshot.
  [Copilot Memory](https://docs.github.com/en/copilot/concepts/agents/copilot-memory).

- **Live code-retrieval systems:** Sourcegraph retrieves relevant snippets
  from keyword search, repository search, and the code graph at question time.
  [Cody context](https://sourcegraph.com/docs/cody/core-concepts/context).
  Google Code Wiki regenerates after changes and links every generated section
  and chat answer directly to code definitions.
  [Google Code Wiki announcement](https://developers.googleblog.com/en/introducing-code-wiki-accelerating-your-code-understanding/).
  Cognition exposes DeepWiki through three on-demand MCP tools and advertises
  auto-refresh for badged repositories.
  [DeepWiki MCP registry](https://github.com/mcp/cognitionai/deepwiki).
  The common property is not “lots of prose”; it is selective retrieval plus
  explicit freshness and source linkage.

- **FSoft CodeWiki:** the upstream design uses dependency analysis,
  hierarchical decomposition, recursive agents, and bottom-up synthesis.
  Those mechanisms solve scale: its published evaluation repositories range
  from 86k to 1.4M LOC. The reported average quality is 68.79%, not executable
  correctness, so generated output remains a derived orientation layer.
  [Paper](https://arxiv.org/html/2510.24428) and
  [implementation](https://github.com/FSoft-AI4Code/CodeWiki).

## Pyrox-specific audit

The following observations are direct measurements of the repository:

| Surface | Size | Assessment |
|---|---:|---|
| `AGENTS.md` + `CLAUDE.md` | 70 lines | Right-sized routing and operating rules |
| Curated `wiki/*.md` | 415 lines | Proportionate and high-signal |
| Generated `codewiki_docs/*.md` | 2,739 lines | Large relative to both code and curated knowledge |
| CodeWiki skill, scripts, and hook | 1,267 lines | More machinery than this repository presently needs |

The separation of authority is well designed: code, then `docs/`, then
`wiki/`, then `codewiki_docs/`. The `/wiki` skill is also correctly on demand,
and its checklist covers dates, links, orphans, source coverage,
contradictions, and active work.

The current state also demonstrates the maintenance failure mode:

- `codewiki_docs/mcp_surface.md` still records the old four-value `Division`
  literal, while the code now includes `relay` and `adaptive`. The freshness
  hook correctly reports `mcp_surface` as stale.
- `wiki/components.md` has the corrected six-value vocabulary, while
  `wiki/domain-concepts.md` still says there are four divisions. The curated
  source/date convention did not prevent an internal contradiction.
- The session-start notice lists the first changed files since the generation
  baseline, which are mostly `.claude` machinery; the actual MCP source that
  caused the useful invalidation can be hidden beyond the display limit.

That does not mean the approach failed. The generated MCP chapter helped
surface the stale closed vocabulary in this work. It means freshness detection
is advisory, not freshness, and two parallel prose layers double the places a
fact can disagree.

## Recommendation for this repository

The following is an inference from the sources and the local measurements, not
a claim made by any one vendor:

1. **Keep the curated wiki as the sole agent knowledge base.** Use it for
   durable architectural decisions, domain vocabulary, non-obvious gotchas,
   and active investigations. Do not mirror ordinary source behavior or API
   reference material.

2. **Relax “sync after every code change.”** Update the wiki when a durable
   invariant, decision, workflow, or gotcha changes. Keep periodic linting and
   source metadata, but prefer claim-level links to exact code/tests for facts
   likely to drift. The append-only log should stay short or be archived; it
   is operational history, not startup context.

3. **Make CodeWiki a tool, not a contract.** Preserve static analysis because
   dependency-aware clustering is useful. Generate architecture docs on
   request for onboarding, audits, or a large refactor. At current scale,
   collapse the committed output to `overview.md` plus the two genuinely deep
   areas, or keep all generated output uncommitted and disposable.

4. **Remove the SessionStart nag if CodeWiki becomes on demand.** A cheap hook
   is technically appropriate, but an alert that remains actionable until a
   multi-agent rewrite is completed creates recurring attention debt. If the
   full generated wiki remains a committed product, move the check to CI/PR
   and make regeneration automatic; that is closer to the OpenAI and Google
   freshness models.

5. **Use a promotion rule:** when a generated chapter reveals a durable,
   verified insight, promote that one insight into `docs/`, an ADR, a test, or
   the curated wiki, then let the generated chapter remain disposable.
   Promote correctness constraints into tests or linters whenever possible.

This preserves the genuinely modern parts of the setup—progressive disclosure,
repo-local knowledge, deterministic validation, and source-grounded
retrieval—without asking a small repository to maintain an enterprise-scale
documentation harness.
