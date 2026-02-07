"""Compatibility package for legacy ``pyrox.api`` imports.

The canonical FastAPI service module now lives at ``pyrox_api_service.app``.
"""

from .app import app

__all__ = ["app"]
