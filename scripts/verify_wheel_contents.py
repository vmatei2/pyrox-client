#!/usr/bin/env python3
"""Verify that the published wheel exposes only the intended pyrox modules.

Usage:
    python scripts/verify_wheel_contents.py
    python scripts/verify_wheel_contents.py dist/pyrox_client-0.2.3-py3-none-any.whl
    python scripts/verify_wheel_contents.py --no-strict

Behavior:
    - Ensures required modules exist in the wheel.
    - Fails if forbidden modules/packages are present.
    - In strict mode (default), fails if unexpected ``pyrox/*.py`` modules exist.
"""

from __future__ import annotations

import argparse
import sys
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that a pyrox wheel exposes only the intended modules.",
        epilog=(
            "Examples:\n"
            "  python scripts/verify_wheel_contents.py\n"
            "  python scripts/verify_wheel_contents.py dist/pyrox_client-0.2.3-py3-none-any.whl\n"
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    wheel_path = args.wheel or _default_wheel_path(args.dist_dir)
    return verify_wheel(wheel_path, strict=not args.no_strict)


if __name__ == "__main__":
    raise SystemExit(main())
