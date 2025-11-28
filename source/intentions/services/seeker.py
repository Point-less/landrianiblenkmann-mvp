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


class ActivateSaleSeekerIntentionService(BaseService):
    """Advance a seeker into an active search."""

    def run(self, *, intention: SaleSeekerIntention) -> SaleSeekerIntention:
        intention.activate_search()
        intention.save(update_fields=["state", "search_activated_at", "updated_at"])
        return intention


class MandateSaleSeekerIntentionService(BaseService):
    """Record a signed mandate for a seeker."""

    def run(self, *, intention: SaleSeekerIntention, signed_on=None) -> SaleSeekerIntention:
        if not intention.search_activated_at:
            raise ValidationError({"state": "Seeker must be active before signing a mandate."})
        intention.sign_mandate(signed_on=signed_on)
        intention.save(update_fields=["state", "mandate_signed_on", "updated_at"])
        return intention


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
    "ActivateSaleSeekerIntentionService",
    "MandateSaleSeekerIntentionService",
    "AbandonSaleSeekerIntentionService",
]
