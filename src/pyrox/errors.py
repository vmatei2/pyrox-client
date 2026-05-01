"""
Custom exceptions for the pyrox client.

Expose a small, predictable hierarchy so users can:
- catch a broad PyroxError for any client-side issue, or
- catch specific errors for targeted handling (e.g., missing race).
"""

from __future__ import annotations

from typing import Optional


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

    def __init__(
        self,
        message: str,
        *,
        season: Optional[int] = None,
        location: Optional[str] = None,
        year: Optional[int] = None,
        available_seasons: Optional[list[int]] = None,
        available_locations: Optional[list[str]] = None,
        available_years: Optional[list[int]] = None,
        suggestions: Optional[list[str]] = None,
    ) -> None:
        super().__init__(message)
        self.season = season
        self.location = location
        self.year = year
        self.available_seasons = available_seasons or []
        self.available_locations = available_locations or []
        self.available_years = available_years or []
        self.suggestions = suggestions or []


class AthleteNotFound(PyroxError, LookupError):
    """
    Raised when a specific athlete is not found in a race.

    Inerit from LookupError to feel natural in 'lookup' code paths.
    """

