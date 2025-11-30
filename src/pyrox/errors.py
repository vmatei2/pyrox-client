"""
Custom exceptions for the pyrox client.

Expose a small, predictable hierarchy so users can:
- catch a broad PyroxError for any client-side issue, or
- catch specific errors for targeted handling (e.g., missing race).
"""

from __future__ import annotations


__all__ = [
    "PyroxError",
    "RaceNotFound",
    "AthleteNotFound",
]


class PyroxError(Exception):
    """Base class for all pyrox-specific errors."""

    pass


class RaceNotFound(PyroxError, LookupError):
    """
    Raised when (season, location) is not present in the manifest.

    Inherit from LookupError to feel natural in 'lookup' code paths.
    """


class AthleteNotFound(PyroxError, LookupError):
    """
    Raised when a specific athlete is not found in a race.

    Inerit from LookupError to feel natural in 'lookup' code paths.
    """


