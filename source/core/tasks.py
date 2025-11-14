"""Core-level background tasks (shared across domains)."""

from __future__ import annotations

import logging

import dramatiq

logger = logging.getLogger(__name__)


@dramatiq.actor
def log_message(message: str) -> None:
    """Simple logging hook used by the health-check endpoint."""

    logger.info("Core log message: %s", message)


__all__ = ["log_message"]
