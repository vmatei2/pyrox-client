"""Compatibility shim for the moved FastAPI service module.

Canonical module path:
    pyrox_api_service.app

This shim keeps legacy imports/entrypoints working during migration.
"""

from pyrox_api_service.app import *  # noqa: F403
from pyrox_api_service.app import app

__all__ = ["app"]
