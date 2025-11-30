import pytest 

def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options to pytest."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests that hit live data",
    )

def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test that hits live data",
    )

def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_integration = config.getoption("--run-integration")

    if run_integration:
        # User explicitly asked for integration tests -> do nothing
        return

    skip_marker = pytest.mark.skip(
        reason="integration tests are skipped by default; use --run-integration to run them",
    )

    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)