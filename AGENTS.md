# Repository Guidelines

## Project Structure & Module Organization
- Docs: `README.md`, `docs/` (mkdocs user docs + `docs/maintainers/` runbooks), and `codewiki_docs/overview.md` (the engineering architecture map).
- Build config: `pyproject.toml` (Hatch build, dependencies, metadata).
- Main client code: `src/pyrox/core.py`; reporting service: `pyrox_api_service/`; frontend: `ui/`

## Build, Test, and Development Commands
- Install (editable): `uv pip install -e .` or `pip install -e .`
- Lint/format: `ruff check .` and `ruff format .` (fallback: `black .` if preferred). Configure via `pyproject.toml`.
- Type check: `mypy src` (if installed locally).

## Coding Style & Naming Conventions
- Style: PEP 8 with Ruff autofix; 4-space indentation; max line length 100 (per ruff/black defaults unless overridden).
- Naming: modules and files snake_case; classes PascalCase; functions and variables snake_case; constants UPPER_SNAKE_CASE.
- Imports: standard lib, third-party, local groups separated by a blank line; prefer explicit imports.

## Testing Guidelines
- Framework: pytest (recommended). Place tests under `tests/` mirroring `src/pyrox/` paths.
- Naming: test files `test_*.py`; functions `test_*`.
- Source the virtual environment located in the .venv folder
- Run: `pytest -q`; coverage (optional) `pytest --cov=pyrox`.
- Aim for coverage of public functions in `core.py` and error paths in `errors.py`.

## Commit & Pull Request Guidelines
- Commits: subject line only, imperative, <=72 chars, no body. Example: "Add client retry and timeouts". Group related changes into one commit; keep noise low. Only add a body if explicitly asked for one on that commit.
- Branches: `feature/<short-desc>`, `fix/<short-desc>`, or `chore/<short-desc>`.
- PRs: include purpose, approach, and testing notes; link issues; add screenshots or logs for API/CLI runs. Ensure lint passes and tests green.

## Security & Configuration Tips
- Service configuration comes from env variables (`PYROX_DUCKDB_PATH` and friends; see `docs/maintainers/reporting-service.md`). Avoid committing secrets; use `.env` locally and CI secrets in pipelines.
- Network calls use `httpx`; set reasonable timeouts and retries in changes. Keep error surfaces mapped to `errors.py` types.

## Production Data Promotion
- `hyrox_analysis` owns the candidate pointer at `latest.json`; do not update it from this repository.
- The live API reads `deploy-current.json`. Promote candidates only through `.github/workflows/refresh-data.yml`; never point Fly directly at `latest.json`.

## Architecture Map

Read `codewiki_docs/overview.md` before substantial code work.

After changing repository files, review the diff for architecture impact.
Update the overview through `/codewiki` only when the change affects at least
one of:

- system boundaries or component ownership;
- a durable domain, data, API, or MCP contract;
- a cross-component request or data flow;
- deployment, runtime, or operator workflow.

Do not edit the overview for local implementation details, routine bug fixes,
tests, styling, or refactors that preserve those contracts. In the final
response for any file-changing task, state one of:

- `Architecture map: updated — <reason>`
- `Architecture map: reviewed; no update needed — <reason>`

This explicit decision is the enforcement point. The `/codewiki` skill owns
overview generation and validation.

## Cross-repository work

This project is one half of a shared data product. Locate the sibling checkout
(`../hyrox_analysis` by default) and read its `AGENTS.md` and
`codewiki_docs/overview.md` when a task crosses the producer/consumer boundary.
If the checkout is elsewhere or unavailable, report that rather than assuming
consumer behavior or claiming end-to-end verification.

- **hyrox_analysis owns:** source discovery and scraping, raw and canonical
  parquet, the race manifest, DuckDB construction and candidate `latest.json`.
- **pyrox-client owns:** Python client filtering, caching and public column
  names; REST/MCP and UI behavior; promotion to `deploy-current.json` and API
  deployment.
- **Inspect both repositories for:** divisions, fields, timing precision, race
  identity, schema compatibility, and publication/promotion changes. Trace the
  actual contract through both sides before deciding which files need edits.
- **Delivery paths are independent:** data publication updates manifest/parquet;
  candidate promotion updates live reporting data; API deployment updates service
  code; a tagged PyPI release updates the installable Python package. A merge or
  API deployment does not upgrade installed packages. Do not infer authorization
  for a package release from a data-backfill request.
- **Verify the affected paths:** focused producer tests and source samples,
  public `PyroxClient.get_race()` with a fresh cache, and live reporting after
  promotion when applicable. Record whether Python checks used the released
  package or repository source; their behavior can differ.
- **Keep scope explicit:** maintain separate git changes and checks in each repo,
  preserve unrelated work, and report commits/PRs, data publication, deployment,
  and package-release status separately. Do not expand a targeted backfill into
  unrelated race repairs or change public column names without task authorization.

Use the two architecture maps for detailed flow and deployment instructions;
keep this section as the entry point rather than duplicating those documents.
