# Release Workflow

This document describes how to cut and publish a new `pyrox-client` release.

## Prerequisites

- You are on an up-to-date branch (typically `main`).
- CI is green.
- You have push permissions for tags.

## 1) Bump Version and Tag

Use the release helper script:

```bash
./scripts/release.sh <version>
```

Example:

```bash
./scripts/release.sh 0.2.4
```

This script:

- updates `src/pyrox/__init__.py` (`__version__`)
- creates a commit
- creates tag `v<version>`

## 2) Validate Locally Before Releasing

Run the same core checks the release workflow relies on:

```bash
uv run --with pytest python -m pytest -q
uv build
uv run python scripts/verify_wheel_contents.py --sdist
```

The package verifier checks both artifacts:

- the wheel contains only the intended `pyrox` package surface
- the source distribution does not include local app, virtualenv, node, or build
  artifacts

## 3) Optional Local Quality Checks

```bash
ruff check .
```

## 4) Publish via GitHub Actions

Push commit and tag:

```bash
git push origin main --tags
```

Publishing is handled by `.github/workflows/release.yml`.

## Notes

- The release workflow depends on `.github/workflows/tests.yml` passing first.
- If a bad tag was created, delete it locally and remotely before recreating:

```bash
git tag -d v<version>
git push --delete origin v<version>
```
