# DOCSEARCH paper analysis and Pyrox adoption plan

## Scope and sources

This note analyses Cheng et al., *Escaping Whack-a-Mole: Optimizing
Documentation as Repo-Specific Playbooks for Coding Agents* (ICML 2026), using
the repository copy at
a local copy of the paper (`papers/16785_Escaping_Whack_a_Mole_Op.pdf`, not
checked into this repository) as the primary source. Page references below are PDF pages. The authors' public
implementation was also inspected at commit
[`48d3c4a`](https://github.com/ccsnow127/docsearch/tree/48d3c4a2d0bd17b843f8751c2936f7a3ffd744db).

## What the paper actually does

The paper is about **optimizing documentation for coding agents**, not about
predictive modelling. For entity `i`, documentation `D` is given to a code
generator, and quality is the proportion of that entity's tests passed by the
generated code:

`phi_i(D) = passed tests for entity i / tests for entity i`.

An entity is "solved" only at `phi_i = 1`; the stated objective is to maximize
the number of solved entities (pp. 2-3, Equations 1-2).

The claimed failure mode is output coupling. If caller `A` depends on callee
`B`, changing `B`'s documentation can produce a different implementation of
`B`, invalidating previously generated `A`. Greedy refinement can therefore
oscillate: each local fix causes a regression elsewhere (pp. 2-3).

DOCSEARCH combines four mechanisms (pp. 3-5; Appendix B):

1. Generate tests with an LLM from the reference source, retain tests that pass
   against the reference implementation, deduplicate them, and use coverage
   feedback to seek more tests (pp. 21, 26-27).
2. Traverse the entity call graph in reverse topological order, stabilizing
   callees before callers. Among eligible siblings, prioritize the entity with
   fewer failing tests (p. 4; Algorithm 2, p. 17).
3. For the selected entity, sample several different subsets of its failures.
   Each branch first diagnoses the documentation's missing knowledge and then
   prescribes a revised specification (pp. 4-5, 20-21).
4. Commit a candidate only if it satisfies a "worthy" no-regression condition;
   otherwise reject it or mark the entity intractable (p. 5; Algorithm 1,
   p. 16).

The central useful idea is not "write longer docs." It is to treat docs as a
versioned, testable interface and refine them from concrete downstream
failures, while protecting already-correct behavior.

## Evidence and how much confidence it deserves

The main benchmark contains 20 Python modules, 227 entities, and 631
ground-truth tests. The search sees separately generated pseudo-tests, while
final scoring uses the ground-truth tests (pp. 5-6, 25-27). That separation is
good experimental hygiene and reduces direct test-set leakage.

Headline solve rates are large: for GPT-4o, DOCSEARCH reports 90.7% versus
58.1% for iterative refinement with topological order, an absolute gain of
32.6 points. Results are also strong for Gemini-2.5-Flash (74.4%) and
Claude-4.5-Sonnet (95.2%) (Table 1, p. 6). The GPT-4o ablation reports losses
of 18.5 points without reverse-topological order, 9.6 without error diversity,
and 7.0 without the worthy gate (Table 2, p. 7). Cross-language generation also
favours optimized documentation over source-only input for Java and Go
(Table 3, p. 8). A small blinded human study reports improved completeness,
correctness, clarity, helpfulness, and specificity (pp. 8-9).

These are credible proof-of-concept results, but not a universal guarantee:

- The sample is 20 deliberately selected, testable, low-external-dependency
  modules with call-graph depth at least three. It is not a representative
  sample of repository maintenance tasks, services, UIs, or data pipelines
  (p. 26).
- Results are point estimates without confidence intervals, repeated-run
  variability, significance tests, or module-clustered uncertainty. Entities
  within a module are not independent observations.
- The human study selects 30 entities from six modules where documentation
  changed substantively. This conditions on successful/visible changes and
  does not measure all attempted entities (p. 8).
- The token-efficiency comparison counts output tokens; it does not establish
  total API cost, input-token cost, wall time, or test-execution cost (p. 9).
- The stated "beam tree search" is operationally closer to diversified
  best-of-W sampling at each step: Algorithm 1 commits the first worthy child
  and does not show multi-depth top-k beam retention or backtracking (p. 16).
- Theorem 1 is an adversarial existence construction with a favourable
  tie-break, not evidence that all greedy refinement is typically `O(1/n)`
  (p. 13).
- Theorem 2 depends on assumptions that define noisy errors as
  non-discriminative or adversarial to the true diagnosis. Its strict claim is
  stronger than the assumptions: likelihood ratios may equal one, in which
  case adding noise need not strictly hurt. The bounds in Assumption 5 also do
  not alone guarantee that ordering posterior probabilities orders refinement
  success unless an additional monotonicity/separation condition holds
  (pp. 14-16). The diversity mechanism remains plausible and empirically
  supported, but the proof should not be read as a general law.
- Dynamic dispatch, hidden dependencies, cycles, and SCC contraction are
  described, but not separately validated in the reported experiments (p. 5).

There is also a material paper-to-code discrepancy. Paper section 3.4 defines a
worthy child as non-regressive for **all** entities. In the current public
implementation,
[`is_worthy`](https://github.com/ccsnow127/docsearch/blob/48d3c4a2d0bd17b843f8751c2936f7a3ffd744db/src/docsearch/search/worthy.py)
excludes the entity being refined, calculates `target_improved` separately,
and `first_worthy` accepts based only on the no-other-regressions boolean. A
candidate can therefore be committed without improving—and even while
degrading—the target. Pyrox should not import that acceptance rule unchanged.

## Why this is relevant to Pyrox

Pyrox has two distinct agent-facing documentation products:

1. Coding-agent context: `AGENTS.md`, maintainers' guides, architecture docs,
   and Python docstrings.
2. Product-agent context: MCP tool names, type schemas, and docstrings that an
   LLM uses to select tools and interpret results.

The repository already has the right architectural seam for callee-before-
caller documentation:

`helpers/data contracts -> ReportingQueries -> FastAPI routes -> MCP tools -> agent answer`

The maintainer guide explicitly documents this layered tool path and states
that MCP docstrings are LLM-facing
([`docs/maintainers/adding-mcp-tools.md`](../maintainers/adding-mcp-tools.md)).
The project also has a useful behavioral oracle: the current suite completes
with **130 passed and 3 skipped**.

However, agent context is already drifting. At the time of this audit,
`AGENTS.md` refers to nonexistent `NOTES.md`, `src/core.py`, `config.py`, and
`openwiki/quickstart.md`, and describes a `core._client` that is not the current
client structure. Those are exactly the ambiguous or false specifications the
paper predicts will induce incorrect agent behavior.

Source-level documentation is uneven. `get_race` has a detailed contract, but
`PyroxClient` and `mmss_to_minutes` have no docstrings; `get_season` is a
one-line description; `get_athlete_in_race` has empty parameter descriptions;
and cache methods omit side effects and corruption/deletion behavior. The MCP
tool descriptions are substantially better, but several still omit operational
semantics that matter to an agent, such as percentile direction, thin-cohort
tail suppression, ambiguity behavior, and exact prerequisite tool flows.

## Recommended Pyrox adaptation

Do not begin with a repository-wide autonomous rewrite. Use a small,
measurement-first pilot.

### 1. Repair the canonical coding playbook

Correct `AGENTS.md`, add a real source map, and state invariant contracts:

- published wheel versus repository-only reporting service;
- DuckDB query -> REST -> MCP layering;
- units (minutes), strict time-window bounds, percentile direction, and cohort
  scope;
- expected exception/degradation behavior;
- the actual commands and test locations.

Generate OpenWiki from that correct source, rather than pointing agents at a
missing generated page.

### 2. Refine one dependency slice from leaves upward

Pilot on either:

- `CacheManager -> PyroxClient`, because tests already cover cache freshness,
  corrupt-cache cleanup, filtering, discovery, and enriched errors; or
- distribution helpers -> `ReportingQueries.distribution` -> REST route ->
  `get_distribution`, because the behavioral contract is deterministic and
  includes important small-sample semantics.

For each entity, document input types and units, output shape, exact boundary
rules, ordering, defaults, exceptions, side effects, and empty/missing-data
behavior. Stabilize lower-level helpers before their callers.

### 3. Build a held-out agent evaluation suite

Ordinary pytest verifies code, not whether documentation helps an agent. Create
two stratified task banks:

- **coding tasks** reconstructed from historical fixes/features, each judged by
  deterministic tests;
- **MCP questions** covering discovery, ambiguous athletes, rankings,
  distributions, thin cohorts, profiles, and invalid filters, judged from
  structured tool calls and response fields rather than an LLM judge alone.

Track task success, valid-call rate, tool-selection accuracy, answer-field
accuracy, calls, tokens, latency, and safety/caveat compliance. Keep a hidden
final test split that is never used to refine docs.

### 4. Use a statistically stricter worthy gate

Agent outputs are stochastic. Evaluate parent and candidate on the same tasks,
model version, seeds, and temperature (paired/common-random-number design).
Commit only when:

- the target task group improves by a predeclared practical margin;
- no critical invariant or previously solved task fails;
- protected groups are non-inferior within a small tolerance;
- token/call cost stays within a declared budget.

With enough tasks, use paired bootstrap intervals over task-level deltas; with a
small bank, require exact non-regression on critical cases and report raw paired
outcomes rather than pretending the estimate is precise. Evaluate all worthy
candidates and select by a declared objective instead of taking the first.

### 5. Add drift controls

Persist the candidate docs, failure batches, model/version, prompts, seeds,
test snapshot, and metrics. Re-run the agent evaluation after tool schema,
response contract, model, or prompt changes. This turns the one-time offline
optimization proposed by the paper into a maintainable process.

## What this does not improve

DOCSEARCH does not improve race-time prediction accuracy, uncertainty
calibration, cohort validity, or model deployment. If predictive modelling is
reintroduced later, it will need a separate model audit, temporal/event-group
validation, leakage checks, unit contracts, interval calibration/coverage
evaluation, and production integration tests. Better playbook documentation
can make those assumptions explicit, but it is not a substitute for that
statistical validation.

## Decision

Adopt the paper's principles—test-grounded documentation, dependency-aware
ordering, diverse failure diagnosis, and no-regression gating—but do not adopt
its headline numbers or current public implementation as guarantees. The
highest-return first step for Pyrox is a corrected canonical agent playbook and
a held-out MCP/coding-agent evaluation harness; only then is automated
documentation search worth its API and maintenance cost.
