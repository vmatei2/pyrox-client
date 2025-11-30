"""
Focused tests for custom exceptions to ensure they can be
imported and raised/caught as expected.
"""

import importlib


def test_errors_are_importable_and_catchable():
    """
    Check that error types exist and behave like standard exceptions.

    Why: Downstream code relies on catching these specific classes to
    differentiate error sources (config vs. HTTP, etc.).
    """
    errors = importlib.import_module("pyrox.errors")

    # Expected base class
    assert hasattr(errors, "PyroxError")

    # Representative specific errors (adjust to match actual definitions)
    specific = [
        name
        for name in ("PyroxError", "RaceNotFound", "AthleteNotFound")
        if hasattr(errors, name)
    ]
    assert specific, "At least one specific error type should exist"

    # Demonstrate raising and catching
    for name in specific:
        exc_type = getattr(errors, name)
        try:
            raise exc_type("boom")
        except exc_type as e:
            assert "boom" in str(e)
        except Exception as e:  # pragma: no cover - safety
            raise AssertionError(f"Unexpected exception path: {e}")

