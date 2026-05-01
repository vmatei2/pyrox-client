#!/usr/bin/env python3
"""Verify that published artifacts expose only the intended pyrox modules.

Usage:
    python scripts/verify_wheel_contents.py
    python scripts/verify_wheel_contents.py dist/pyrox_client-0.2.3-py3-none-any.whl
    python scripts/verify_wheel_contents.py --sdist dist/pyrox_client-0.2.3.tar.gz
    python scripts/verify_wheel_contents.py --no-strict

Behavior:
    - Ensures required modules exist in the wheel.
    - Fails if forbidden modules/packages are present.
    - Fails if the sdist contains app, virtualenv, node, or local build artifacts.
    - In strict mode (default), fails if unexpected ``pyrox/*.py`` modules exist.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from pathlib import Path

REQUIRED_MODULES = {
    "pyrox/__init__.py",
    "pyrox/core.py",
    "pyrox/reporting.py",
    "pyrox/errors.py",
    "pyrox/constants.py",
}

FORBIDDEN_PATH_PREFIXES = (
    "pyrox/api/",
    "pyrox/helpers.py",
)

ALLOWED_MODULES = REQUIRED_MODULES

FORBIDDEN_SDIST_PARTS = {
    ".venv",
    ".venv-pyrox-test",
    "__pycache__",
    "dist",
    "docs",
    "example_notebooks",
    "node_modules",
    "pyrox_api_service",
    "scripts",
    "ui",
}

FORBIDDEN_SDIST_NAMES = {
    "pyrox_duckdb",
}


def _default_wheel_path(dist_dir: Path) -> Path:
    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        raise FileNotFoundError(
            f"No wheel found in '{dist_dir}'. Build first, e.g. `uv build --wheel`."
        )
    return wheels[-1]


def _pyrox_python_modules(archive_names: set[str]) -> set[str]:
    return {
        name
        for name in archive_names
        if name.startswith("pyrox/") and name.endswith(".py")
    }


def verify_wheel(path: Path, strict: bool = True) -> int:
    with zipfile.ZipFile(path) as wheel:
        names = set(wheel.namelist())

    pyrox_modules = _pyrox_python_modules(names)
    missing_required = sorted(REQUIRED_MODULES - pyrox_modules)
    forbidden_present = sorted(
        name
        for name in names
        if any(name.startswith(prefix) for prefix in FORBIDDEN_PATH_PREFIXES)
    )
    unexpected_modules = sorted(pyrox_modules - ALLOWED_MODULES) if strict else []

    errors: list[str] = []
    if missing_required:
        errors.append(
            "Missing required modules:\n  - " + "\n  - ".join(missing_required)
        )
    if forbidden_present:
        errors.append(
            "Forbidden modules found:\n  - " + "\n  - ".join(forbidden_present)
        )
    if unexpected_modules:
        errors.append(
            "Unexpected pyrox modules in strict mode:\n  - "
            + "\n  - ".join(unexpected_modules)
        )

    print(f"Inspecting wheel: {path}")
    print(f"Detected pyrox modules ({len(pyrox_modules)}):")
    for module in sorted(pyrox_modules):
        print(f"  - {module}")

    if errors:
        print("\nVERIFICATION FAILED")
        for error in errors:
            print(f"\n{error}")
        return 1

    print("\nVERIFICATION PASSED")
    return 0


def _default_sdist_path(dist_dir: Path) -> Path:
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if not sdists:
        raise FileNotFoundError(
            f"No sdist found in '{dist_dir}'. Build first, e.g. `uv build`."
        )
    return sdists[-1]


def _strip_sdist_root(name: str) -> Path:
    path = Path(name)
    parts = path.parts
    if len(parts) <= 1:
        return Path("")
    return Path(*parts[1:])


def verify_sdist(path: Path) -> int:
    with tarfile.open(path, "r:gz") as sdist:
        names = sdist.getnames()

    forbidden = []
    for name in names:
        relative = _strip_sdist_root(name)
        parts = set(relative.parts)
        if parts & FORBIDDEN_SDIST_PARTS or relative.name in FORBIDDEN_SDIST_NAMES:
            forbidden.append(name)

    print(f"Inspecting sdist: {path}")
    print(f"Detected sdist entries: {len(names)}")

    if forbidden:
        print("\nVERIFICATION FAILED")
        print("\nForbidden sdist entries found:")
        for name in sorted(forbidden)[:50]:
            print(f"  - {name}")
        if len(forbidden) > 50:
            print(f"  ... and {len(forbidden) - 50} more")
        return 1

    print("\nVERIFICATION PASSED")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that a pyrox wheel exposes only the intended modules.",
        epilog=(
            "Examples:\n"
            "  python scripts/verify_wheel_contents.py\n"
            "  python scripts/verify_wheel_contents.py dist/pyrox_client-0.2.3-py3-none-any.whl\n"
            "  python scripts/verify_wheel_contents.py --sdist\n"
            "  python scripts/verify_wheel_contents.py --no-strict"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "wheel",
        nargs="?",
        type=Path,
        help="Path to wheel. Defaults to newest wheel in ./dist.",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path("dist"),
        help="Directory to search when wheel path is omitted (default: dist).",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Allow additional pyrox modules beyond the current allowlist.",
    )
    parser.add_argument(
        "--sdist",
        nargs="?",
        const=True,
        default=None,
        help=(
            "Also verify an sdist. Provide a path or omit the value to use the "
            "newest .tar.gz in --dist-dir."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    status = 0

    wheel_path = args.wheel or _default_wheel_path(args.dist_dir)
    status |= verify_wheel(wheel_path, strict=not args.no_strict)

    if args.sdist is not None:
        sdist_path = (
            _default_sdist_path(args.dist_dir)
            if args.sdist is True
            else Path(args.sdist)
        )
        status |= verify_sdist(sdist_path)

    return status


if __name__ == "__main__":
    raise SystemExit(main())
