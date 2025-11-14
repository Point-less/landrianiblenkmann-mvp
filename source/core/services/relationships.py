"""Services for linking contacts and agents."""

from datetime import date

from django.core.exceptions import ValidationError

from core.models import Agent, Contact, ContactAgentRelationship
from utils.services import BaseService


class LinkContactAgentService(BaseService):
    """Ensure a relationship exists between a contact and an agent."""

    def run(
        self,
        *,
        contact: Contact,
        agent: Agent,
        status: str | None = None,
        relationship_notes: str | None = None,
        started_on: date | None = None,
        ended_on: date | None = None,
    ) -> ContactAgentRelationship:
        if status and status not in ContactAgentRelationship.Status.values:
            raise ValidationError({"status": "Invalid relationship status."})

        defaults = {
            "status": status or ContactAgentRelationship.Status.ACTIVE,
            "relationship_notes": relationship_notes or "",
            "started_on": started_on,
            "ended_on": ended_on,
        }
        link, created = ContactAgentRelationship.objects.get_or_create(
            contact=contact,
            agent=agent,
            defaults=defaults,
        )

        if created:
            return link

        updates = {}
        for field, value in defaults.items():
            if value is not None and getattr(link, field) != value:
                updates[field] = value

        if updates:
            for field, value in updates.items():
                setattr(link, field, value)
            link.save(update_fields=list(updates.keys()) + ["updated_at"])
        return link


__all__ = ["LinkContactAgentService"]
