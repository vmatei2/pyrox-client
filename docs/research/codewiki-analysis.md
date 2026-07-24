# CodeWiki: paper and implementation analysis

Date reviewed: 2026-07-19  
Paper: [CodeWiki: Evaluating AI's Ability to Generate Holistic Documentation for Large-Scale Codebases](https://arxiv.org/abs/2510.24428)  
Repository: [FSoft-AI4Code/CodeWiki](https://github.com/FSoft-AI4Code/CodeWiki)  
Source snapshot inspected: [`763d08f`](https://github.com/FSoft-AI4Code/CodeWiki/tree/763d08f2c7a95048ee979c520a12e268ef98344c)

## Executive summary

CodeWiki generates a human-facing wiki for an entire repository. It uses static analysis to identify code components and their relationships, groups those components into a module hierarchy, lets agents write leaf-module documentation, and then summarizes the leaf documents upward into parent-module and repository overviews. The output includes Markdown, cross-links, and Mermaid diagrams.

This is different from DocSearch. CodeWiki asks, “Can we explain the whole repository in a navigable way?” DocSearch asks, “Are these behavioral instructions precise enough for an agent to reconstruct code that passes tests?” CodeWiki has breadth and architectural context; DocSearch has executable behavioral feedback. They are complementary.

For Pyrox, the sensible experiment is to generate a separate architecture wiki for `src/pyrox`, `pyrox_api_service`, and `ui/src`, while continuing to use DocSearch for exact behavioral documentation of critical surfaces such as `pyrox_api_service/mcp_tools.py`.

## The problem it addresses

Function-level documentation does not explain how a large system fits together. CodeWiki targets repository-level questions:

- What are the major modules?
- Which modules depend on each other?
- What are the main entry points and data flows?
- How should a new developer navigate the codebase?
- How can detailed component documentation be rolled up into architectural summaries?

The paper calls CodeWiki a **semi-agentic** framework. Its central scaling idea is hierarchical decomposition: split a repository into bounded modules, document the leaves, and synthesize higher-level documents from the results. [Paper, Sections 1 and 3](https://arxiv.org/pdf/2510.24428#page=1)

## Pipeline

### 1. Static repository analysis

CodeWiki parses source files into components such as functions, methods, classes, and modules. It extracts calls, imports, inheritance, and other structural relationships to construct a directed dependency graph. The paper describes this as Tree-sitter-based parsing normalized into a common `depends_on` relation. [Paper, Section 3.1](https://arxiv.org/pdf/2510.24428#page=4)

The current repository uses language-specific analyzers and a dependency graph builder. Python has a native AST path, while several other languages use Tree-sitter. [Dependency graph builder](https://github.com/FSoft-AI4Code/CodeWiki/blob/763d08f2c7a95048ee979c520a12e268ef98344c/codewiki/src/be/dependency_analyzer/dependency_graphs_builder.py#L18-L70)

### 2. Hierarchical module decomposition

CodeWiki identifies potential core or entry components and asks an LLM to group them into coherent modules. It recursively repeats clustering for groups that remain above the token threshold. If the repository or module already fits under the threshold, clustering is skipped and it is documented as a whole. [Clustering implementation](https://github.com/FSoft-AI4Code/CodeWiki/blob/763d08f2c7a95048ee979c520a12e268ef98344c/codewiki/src/be/cluster_modules.py#L75-L110)

The result is a module tree rather than a flat list of files. Modules are intended to represent features or architectural responsibilities, although the grouping remains an LLM judgment.

### 3. Agent-based leaf documentation

Each leaf module is assigned an agent with:

- source code for its core components;
- the repository's module tree;
- a tool for reading additional components;
- a constrained Markdown file editor;
- for complex modules, a delegation tool that creates submodules and sub-agents.

The agent writes module documentation and Mermaid diagrams. [Agent setup](https://github.com/FSoft-AI4Code/CodeWiki/blob/763d08f2c7a95048ee979c520a12e268ef98344c/codewiki/src/be/pydantic_ai_backend.py#L56-L121)

Delegation is genuine agent delegation: a parent agent can propose submodule specifications, update the module tree, and invoke new agents recursively. [Delegation implementation](https://github.com/FSoft-AI4Code/CodeWiki/blob/763d08f2c7a95048ee979c520a12e268ef98344c/codewiki/src/be/agent_tools/generate_sub_module_documentations.py#L16-L91)

### 4. Bottom-up synthesis

CodeWiki processes children before parents. After leaf documents exist, an LLM reads the immediate child documentation and produces a parent overview. It repeats this up the tree and finally generates `overview.md` for the repository. [Documentation orchestrator](https://github.com/FSoft-AI4Code/CodeWiki/blob/763d08f2c7a95048ee979c520a12e268ef98344c/codewiki/src/be/documentation_generator.py#L157-L241)

The paper calls this “dynamic programming-inspired.” In implementation terms, that mostly means bottom-up reuse of already-generated child documents, caching, and skipping work whose artifact already exists. It is not an optimization search like DocSearch.

## Inputs and outputs

The ordinary CLI takes the current Git repository as its main input. It does **not** require a target file or test file. Optional controls include include/exclude patterns, focus paths, documentation style, custom instructions, token thresholds, and maximum hierarchy depth. [CLI options](https://github.com/FSoft-AI4Code/CodeWiki/blob/763d08f2c7a95048ee979c520a12e268ef98344c/codewiki/cli/commands/generate.py#L211-L307)

Typical output is:

```text
generated-wiki/
├── overview.md
├── <module>.md
├── module_tree.json
├── first_module_tree.json
├── metadata.json
└── index.html              # optional GitHub Pages viewer
```

The Markdown includes architecture, dependency, data-flow, and sequence diagrams where the agent considers them useful. [README output description](https://github.com/FSoft-AI4Code/CodeWiki/blob/763d08f2c7a95048ee979c520a12e268ef98344c/README.md#L311-L340)

## What is actually agentic?

There are two current modes:

1. **One-shot CLI/web mode:** CodeWiki owns the LLM calls. Agents inspect code, write docs through tools, and may delegate submodules to agents.
2. **MCP/IDE-driven mode:** CodeWiki supplies deterministic tools for analysis, source retrieval, module-tree persistence, Mermaid-validated writing, and incremental state. The host agent performs the clustering and writing itself. [MCP skill workflow](https://github.com/FSoft-AI4Code/CodeWiki/blob/763d08f2c7a95048ee979c520a12e268ef98344c/skills/codewiki-wiki-generator/SKILL.md)

The system is agentic because an LLM chooses which components to inspect, writes and revises files through tools, and can delegate work. Static analysis, processing order, persistence, and diagram validation remain deterministic scaffolding.

## Evaluation in the paper

The authors introduce CodeWikiBench because BLEU/ROUGE-style similarity is unsuitable for repository documentation. The benchmark:

1. derives a hierarchical rubric from a project's official documentation;
2. asks multiple judge models whether generated documentation satisfies concrete leaf requirements;
3. aggregates binary leaf scores upward with weights;
4. propagates judge disagreement as a reliability measure.

[Paper, Section 4](https://arxiv.org/pdf/2510.24428#page=6)

Across seven repositories, the paper reports:

- CodeWiki: **68.79%** average;
- closed-source DeepWiki: **64.06%**;
- CodeWiki won on five of seven repositories;
- CodeWiki was weaker than DeepWiki on the C and C++ repositories.

[Paper, Table 1 and Section 5](https://arxiv.org/pdf/2510.24428#page=7)

These figures are rubric-coverage scores from LLM judges. They are not executable correctness scores and do not establish that every generated claim is factually correct. The human evaluation was only a pilot involving three people, three repositories, and nine comparisons. [Paper limitations](https://arxiv.org/pdf/2510.24428#page=10)

## Paper versus current repository

The codebase has evolved since the evaluated paper:

- The paper evaluates seven languages; the current README lists nine, adding Kotlin and PHP. [Current README](https://github.com/FSoft-AI4Code/CodeWiki/blob/763d08f2c7a95048ee979c520a12e268ef98344c/README.md#L138-L152)
- The current project supports API providers, Claude Code/Codex subscription routing, incremental updates, and a fine-grained MCP server.
- The paper describes delegation criteria including cyclomatic complexity, nesting depth, semantic diversity, and context utilization. The current `is_complex_module` heuristic is substantially simpler: a module is complex when its components span more than one file; recursive delegation is additionally bounded by token and depth thresholds. [Current heuristic](https://github.com/FSoft-AI4Code/CodeWiki/blob/763d08f2c7a95048ee979c520a12e268ef98344c/codewiki/src/be/utils.py#L36-L44)
- Paper experiments used a maximum delegation depth of three and a 32,768-token leaf threshold. Current CLI defaults are depth two and 16,000 tokens per leaf module.

The paper therefore explains the research design, but current source is the authority for installation and runtime behavior.

## Important limitations and risks

### No behavioral correctness loop

Generation does not run the project's tests and does not refine docs based on failures. A polished diagram or explanation can still be wrong. CodeWikiBench is a separate paper evaluation, not a validator executed during `codewiki generate`.

### LLM-based architecture decisions

Module grouping and narrative synthesis are LLM judgments. Static analysis supplies evidence, but the resulting feature boundaries and architectural interpretation can still be arbitrary or incomplete.

### Simpler delegation than the paper suggests

Current complexity detection does not implement the full set of metrics described in the paper. It is best understood as recursive multi-file/token partitioning, not a sophisticated complexity optimizer.

### Security issue in current clustering

The current CLI clustering path parses LLM-generated text with unrestricted Python `eval`. That creates a code-execution risk, especially when analyzing an untrusted repository that can inject instructions into model context or when using an untrusted model endpoint. [Clustering parser](https://github.com/FSoft-AI4Code/CodeWiki/blob/763d08f2c7a95048ee979c520a12e268ef98344c/codewiki/src/be/cluster_modules.py#L112-L139)

The MCP mode avoids asking CodeWiki's internal LLM to emit this value—the host agent passes a structured module tree—but it should still be treated as beta tooling.

### GPT-5 temperature compatibility

The API-backed implementation currently sets temperature to `0.0` in model settings and single-shot calls. GPT-5 endpoints that only accept the default temperature can therefore fail in the same way observed with DocSearch. [LLM service](https://github.com/FSoft-AI4Code/CodeWiki/blob/763d08f2c7a95048ee979c520a12e268ef98344c/codewiki/src/be/llm_services.py#L29-L53)

Using the Codex subscription backend avoids depending on this specific OpenAI-compatible Chat Completions path.

### Project maturity

The package describes itself as Beta. The inspected repository currently contains one MCP smoke-test script rather than a broad automated unit-test suite. Generated content should be reviewed before publication.

## CodeWiki versus DocSearch

| Dimension | CodeWiki | DocSearch |
|---|---|---|
| Primary goal | Navigable repository wiki | Behaviorally sufficient agent documentation |
| Scope | Whole repository, modules, cross-file architecture | Target file/module and individual entities |
| Source access | Agents can inspect source code | Regeneration agent reconstructs target from docs |
| Tests required | No | Yes, for meaningful φ |
| Feedback during generation | Mostly one-pass agent writing and synthesis | Iterative black-box search driven by test results |
| Quality signal | Separate LLM-judge rubric benchmark | Executable test pass rate φ |
| Main audience | Humans learning and maintaining the system | Agents reconstructing exact behavior |
| Best Pyrox use | Architecture, onboarding, cross-service/client/UI flows | Precise MCP/API behavioral contracts |

## Recommended Pyrox experiment

Do not point the first run at the existing `docs/` or `wiki/` directories. Pyrox already has maintained documentation and an OpenWiki output. Use a separate directory such as `codewiki_docs/` so the result can be reviewed and compared without overwriting anything.

Focus the first run on:

- `src/pyrox` — public Python client;
- `pyrox_api_service` — service, reporting queries, MCP app and tools;
- `ui/src` — JavaScript/React client and its API/data flow.

Explicitly exclude:

- `.venv`, generated runs and caches;
- existing `docs/`, `wiki/`, and `papers/`;
- notebooks and large generated images;
- `ui/node_modules` and build output;
- `ui/ios`, because Swift is not currently among CodeWiki's supported analyzers.

Useful questions for reviewing the result:

1. Does the module tree separate the Python client, reporting service, MCP surface, and UI appropriately?
2. Does the repository overview correctly describe data flow from UI/MCP request to service/query/client layers?
3. Are module links and diagrams grounded in real imports and calls?
4. Does it expose architectural gaps or duplicated concepts that the current OpenWiki misses?
5. Are claims about API behavior consistent with tests and existing ADRs?

If the result is useful, keep CodeWiki for broad architecture and incremental wiki refreshes. Continue using DocSearch selectively for high-risk behavioral interfaces. Do not replace hand-written ADRs, operational runbooks, or test-backed contracts with generated prose.
