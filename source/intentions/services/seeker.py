"""Seeker-facing services for intentions."""

from django.core.exceptions import ValidationError

from core.models import Agent, Contact, Currency
from intentions.models import SeekerIntention
from utils.services import BaseService
from utils.authorization import SEEKER_INTENTION_CREATE, SEEKER_INTENTION_ABANDON


class CreateSeekerIntentionService(BaseService):
    """Capture an inbound buyer inquiry before it becomes an opportunity."""

    required_action = SEEKER_INTENTION_CREATE

    def run(
        self,
        *,
        contact: Contact,
        agent: Agent,
        operation_type,
        budget_min=None,
        budget_max=None,
        currency: Currency | None = None,
        desired_features: dict | None = None,
        notes: str | None = None,
    ) -> SeekerIntention:
        return SeekerIntention.objects.create(
            contact=contact,
            agent=agent,
            operation_type=operation_type,
            budget_min=budget_min,
            budget_max=budget_max,
            currency=currency,
            desired_features=desired_features or {},
            notes=notes or "",
        )


class AbandonSeekerIntentionService(BaseService):
    """Mark a seeker intention as abandoned."""

    required_action = SEEKER_INTENTION_ABANDON

    def run(self, *, intention: SeekerIntention, reason: str | None = None) -> SeekerIntention:
        intention.abandon(reason=reason)
        update_fields = ["state", "updated_at"]
        if reason:
            update_fields.append("notes")
        intention.save(update_fields=update_fields)
        return intention


__all__ = [
    "CreateSeekerIntentionService",
    "AbandonSeekerIntentionService",
]
