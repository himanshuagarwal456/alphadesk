"""FastAPI application for AlphaDesk (Phase 3).

Requires the optional ``[server]`` extra::

    pip install "alphadesk[server]"
    alphadesk-api
"""

from __future__ import annotations

from .app import create_app, main

__all__ = ["create_app", "main"]
