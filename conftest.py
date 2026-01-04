from __future__ import annotations

import pytest 
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _pytest.config import Parser

def pytest_addoption(parser: "Parser") -> None:
    """Add custom command line options to pytest."""

    group = parser.getgroup("pyrox")
    group.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests that hit live data",
    )
    group.addoption(
        "--only-integration",
        action="store_true",
        default=False,
        help="run only integration tests that hit live data",
    )
    


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test that hits live data",
    )

def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    only_integration = config.getoption("--only-integration")
    if only_integration:
        # only integration tests -> skip all non-integration
        skip_marker = pytest.mark.skip(
            reason="only running integration tests; skipping non-integration",
        )

        for item in items:
            if "integration" not in item.keywords:
                item.add_marker(skip_marker)
        return
    run_integration = config.getoption("--run-integration")

    if run_integration:
        # asked for integration tests -> do nothing --> run all
        return

    skip_marker = pytest.mark.skip(
        reason="integration tests are skipped by default; use --run-integration to run them",
    )

    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)
