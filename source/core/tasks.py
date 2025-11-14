"""Core-level background tasks (shared across domains)."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, MutableMapping
from datetime import datetime

import dramatiq

from core.integrations.tokkobroker import fetch_tokkobroker_properties
from core.models import TokkobrokerProperty

logger = logging.getLogger(__name__)


def _parse_tokkobroker_date(raw: str | None) -> datetime.date | None:
    if not raw:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    logger.debug("Unable to parse Tokkobroker date '%s'", raw)
    return None


def _extract_created_at(payload: Mapping[str, object]) -> str | None:
    quick_data = payload.get("quick_data")
    if isinstance(quick_data, Mapping):
        data = quick_data.get("data")
        if isinstance(data, Mapping):
            created_at = data.get("created_at")
            if isinstance(created_at, str):
                return created_at
    return None


def sync_tokkobroker_registry(
    payloads: Iterable[MutableMapping[str, object]] | None = None,
) -> int:
    """Synchronize the Tokkobroker property registry.

    Returns the number of records processed.
    """

    if payloads is None:
        payloads = fetch_tokkobroker_properties()
    count = 0

    for payload in payloads:
        if not isinstance(payload, MutableMapping):  # defensive: skip malformed entries
            logger.debug("Skipping malformed Tokkobroker payload: %r", payload)
            continue

        tokko_id = payload.get("id")
        ref_code = payload.get("ref_code")
        address = payload.get("address")
        created_at_raw = _extract_created_at(payload)

        if not isinstance(tokko_id, int):
            logger.debug("Skipping Tokkobroker payload without integer 'id': %r", payload)
            continue

        defaults = {
            "ref_code": str(ref_code or ""),
            "address": str(address or ""),
            "tokko_created_at": _parse_tokkobroker_date(created_at_raw),
        }

        TokkobrokerProperty.objects.update_or_create(
            tokko_id=tokko_id,
            defaults=defaults,
        )
        count += 1

    return count


@dramatiq.actor
def sync_tokkobroker_properties_task() -> None:
    """Dramatiq entry-point for synchronizing Tokkobroker properties."""

    processed = sync_tokkobroker_registry()
    logger.info("Synced %s Tokkobroker properties", processed)


@dramatiq.actor
def log_message(message: str) -> None:
    logger.info("Core log message: %s", message)


__all__ = [
    "sync_tokkobroker_registry",
    "sync_tokkobroker_properties_task",
    "log_message",
]
