"""Compatibility entrypoint: ``uvicorn src.api.main:app`` still works."""

from backend.main import app

__all__ = ["app"]
