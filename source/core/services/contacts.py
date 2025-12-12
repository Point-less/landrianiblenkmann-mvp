"""Service objects for managing contacts."""

from typing import Any

from django.core.exceptions import ValidationError

from core.models import Contact
from utils.services import BaseService
from utils.authorization import CONTACT_CREATE, CONTACT_UPDATE


class CreateContactService(BaseService):
    """Create a contact record with the basic profile data."""

    required_action = CONTACT_CREATE

    def run(
        self,
        *,
        first_name: str,
        last_name: str = "",
        email: str,
        phone_number: str | None = None,
        full_address: str | None = None,
        tax_id: str | None = None,
        tax_condition: str | None = None,
        notes: str | None = None,
    ) -> Contact:
        return Contact.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            full_address=full_address or "",
            tax_id=tax_id or "",
            tax_condition=tax_condition or "",
            notes=notes or "",
        )


class UpdateContactService(BaseService):
    """Patch the mutable fields of a contact."""

    required_action = CONTACT_UPDATE

    editable_fields = {"first_name", "last_name", "email", "phone_number", "notes", "full_address", "tax_id", "tax_condition"}

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
