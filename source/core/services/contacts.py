"""Service objects for managing contacts."""

from typing import Any

from django.core.exceptions import ValidationError

from core.models import Contact
from utils.services import BaseService


class CreateContactService(BaseService):
    """Create a contact record with the basic profile data."""

    def run(
        self,
        *,
        first_name: str,
        last_name: str = "",
        email: str | None = None,
        phone_number: str | None = None,
        notes: str | None = None,
    ) -> Contact:
        return Contact.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email or "",
            phone_number=phone_number or "",
            notes=notes or "",
        )


class UpdateContactService(BaseService):
    """Patch the mutable fields of a contact."""

    editable_fields = {"first_name", "last_name", "email", "phone_number", "notes"}

    def run(self, *, contact: Contact, **changes: Any) -> Contact:
        if not changes:
            return contact

        invalid = set(changes) - self.editable_fields
        if invalid:
            raise ValidationError({"fields": f"Unsupported contact fields: {sorted(invalid)}"})

        for field, value in changes.items():
            normalized = value if value is not None else ""
            setattr(contact, field, normalized)

        contact.full_clean()
        update_fields = list(changes.keys()) + ["updated_at"]
        contact.save(update_fields=update_fields)
        return contact


__all__ = ["CreateContactService", "UpdateContactService"]
