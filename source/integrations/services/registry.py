from __future__ import annotations

from integrations.models import TokkobrokerProperty
from utils.services import BaseService


class ClearTokkobrokerRegistryService(BaseService):
    """Remove all TokkobrokerProperty rows."""

    atomic = True

    def run(self, *, actor=None):
        deleted, _ = TokkobrokerProperty.objects.all().delete()
        return deleted


class TokkobrokerPropertiesQuery(BaseService):
    """Return latest Tokkobroker properties."""

    def run(self, *, actor=None, limit: int | None = None):
        qs = TokkobrokerProperty.objects.order_by("-created_at")
        if limit:
            qs = qs[:limit]
        return qs


class UpsertTokkobrokerPropertyService(BaseService):
    """Create or update a TokkobrokerProperty from sync payload."""

    def run(self, *, tokko_id: int, ref_code: str, address: str, tokko_created_at=None):
        TokkobrokerProperty.objects.update_or_create(
            tokko_id=tokko_id,
            defaults={
                "ref_code": ref_code,
                "address": address,
                "tokko_created_at": tokko_created_at,
            },
        )
        return tokko_id


__all__ = [
    "ClearTokkobrokerRegistryService",
    "TokkobrokerPropertiesQuery",
    "UpsertTokkobrokerPropertyService",
]
