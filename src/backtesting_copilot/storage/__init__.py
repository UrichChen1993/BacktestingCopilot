"""SQLite persistence for configs, levels, schedules, trades and AI reports."""

from .db import init_db

__all__ = ["init_db"]
