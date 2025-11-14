"""Property registry services."""

from datetime import date

from core.models import Property
from integrations.models import TokkobrokerProperty
from utils.services import BaseService


class CreatePropertyService(BaseService):
    """Create a property shell that can later receive marketing data."""

    def run(
        self,
        *,
        name: str,
        reference_code: str,
    ) -> Property:
        return Property.objects.create(
            name=name,
            reference_code=reference_code,
        )


class RegisterTokkobrokerPropertyService(BaseService):
    """Upsert a Tokkobroker-sourced property snapshot."""

    def run(
        self,
        *,
        tokko_id: int,
        ref_code: str,
        address: str | None = None,
        tokko_created_at: date | None = None,
    ) -> TokkobrokerProperty:
        record, _ = TokkobrokerProperty.objects.update_or_create(
            tokko_id=tokko_id,
            defaults={
                "ref_code": ref_code,
                "address": address or "",
                "tokko_created_at": tokko_created_at,
            },
        )
        return record


__all__ = [
    "CreatePropertyService",
    "RegisterTokkobrokerPropertyService",
]
