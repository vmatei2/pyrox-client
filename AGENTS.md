# Repository Guidelines

## Project Structure & Module Organization
- Docs: `README.md`, `NOTES.md`.
- Build config: `pyproject.toml` (Hatch build, dependencies, metadata).
- Main client code: `src/core.py`

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
- Source the virutal environment located in .venv folder
- Run: `pytest -q`; coverage (optional) `pytest --cov=pyrox`.
- Aim for coverage of public functions in `core.py` and error paths in `errors.py`.

## Commit & Pull Request Guidelines
- Commits: concise imperative subject (<=72 chars). Example: "Add client retry and timeouts". Group related changes; keep noise low.
- Branches: `feature/<short-desc>`, `fix/<short-desc>`, or `chore/<short-desc>`.
- PRs: include purpose, approach, and testing notes; link issues; add screenshots or logs for API/CLI runs. Ensure lint passes and tests green.

## Security & Configuration Tips
- API URL and key: prefer env variables consumed in `config.py`. Avoid committing secrets; use `.env` locally and CI secrets in pipelines.
- Network calls: `core._client` uses `httpx`; set reasonable timeouts and retries in changes. Keep error surfaces mapped to `errors.py` types.
