"""
Custom exceptions for the pyrox client.

Expose a small, predictable hierarchy so users can:
- catch a broad PyroxError for any client-side issue, or
- catch specific errors for targeted handling (e.g., missing race).
"""

from __future__ import annotations


__all__ = [
    "PyroxError",
    "ConfigError",
    "ManifestUnavailable",
    "ApiError",
    "RaceNotFound",
    "ParquetReadError",
]


class PyroxError(Exception):
    """Base class for all pyrox-specific errors."""
    pass


class ConfigError(PyroxError):
    """
    Raised when the client configuration is invalid or incomplete.
    Example: bucket URI not set or malformed.
    """
    pass


class ManifestUnavailable(PyroxError):
    """
    Raised when the manifest cannot be retrieved or parsed.

    Typical reasons:
      - Network/S3 access problems
      - File missing or not public
      - CSV missing required columns (season, location, path)
    """
    pass


class ApiError(PyroxError):
    """Raised when an HTTP call to the Pyrox API fails."""
    pass


class RaceNotFound(PyroxError, LookupError):
    """
    Raised when (season, location) is not present in the manifest.

    Inherit from LookupError to feel natural in 'lookup' code paths.
    """
    pass


class ParquetReadError(PyroxError, IOError):
    """
    Raised when the parquet for a race cannot be read (S3 read failure,
    corrupted object, incompatible parquet version, etc.).
    """
    pass
