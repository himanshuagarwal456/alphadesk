"""Persistent AlphaDesk web application (Phase 9).

Static assets live under ``tradingagents/web/static`` and are mounted at
``/app`` by the FastAPI factory. The UI talks to the versioned ``/v1`` API.
"""

from __future__ import annotations

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent / "static"

__all__ = ["STATIC_DIR"]
