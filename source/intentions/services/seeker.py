"""Seeker-facing services for sale intentions."""

from django.core.exceptions import ValidationError

from core.models import Agent, Contact, Currency
from intentions.models import SaleSeekerIntention
from utils.services import BaseService


class CreateSaleSeekerIntentionService(BaseService):
    """Capture an inbound buyer inquiry before it becomes an opportunity."""

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
    ) -> SaleSeekerIntention:
        return SaleSeekerIntention.objects.create(
            contact=contact,
            agent=agent,
            operation_type=operation_type,
            budget_min=budget_min,
            budget_max=budget_max,
            currency=currency,
            desired_features=desired_features or {},
            notes=notes or "",
        )


class AbandonSaleSeekerIntentionService(BaseService):
    """Mark a seeker intention as abandoned."""

    def run(self, *, intention: SaleSeekerIntention, reason: str | None = None) -> SaleSeekerIntention:
        intention.abandon(reason=reason)
        update_fields = ["state", "updated_at"]
        if reason:
            update_fields.append("notes")
        intention.save(update_fields=update_fields)
        return intention


__all__ = [
    "CreateSaleSeekerIntentionService",
    "AbandonSaleSeekerIntentionService",
]
