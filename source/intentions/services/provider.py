"""Provider-facing services for sale intentions."""

from typing import Any, Mapping

from django.core.exceptions import ValidationError

from core.models import Agent, Contact, Currency, Property
from integrations.models import TokkobrokerProperty
from intentions.models import SaleProviderIntention, SaleValuation
from opportunities.services import CreateOpportunityService
from utils.services import BaseService


class CreateSaleProviderIntentionService(BaseService):
    """Register a new provider intention before it becomes an opportunity."""

    def run(
        self,
        *,
        owner: Contact,
        agent: Agent,
        property: Property,
        operation_type,
        documentation_notes: str | None = None,
    ) -> SaleProviderIntention:
        return SaleProviderIntention.objects.create(
            owner=owner,
            agent=agent,
            property=property,
            operation_type=operation_type,
            documentation_notes=documentation_notes or "",
        )


class DeliverSaleValuationService(BaseService):
    """Attach a valuation and advance the provider intention FSM."""

    def run(
        self,
        *,
        intention: SaleProviderIntention,
        amount,
        currency: Currency,
        notes: str | None = None,
    ) -> SaleValuation:
        intention.deliver_valuation(amount=amount, currency=currency, notes=notes)
        intention.save(update_fields=["state", "valuation", "updated_at"])
        return intention.valuation  # type: ignore[return-value]


class WithdrawSaleProviderIntentionService(BaseService):
    """Withdraw an intention that will no longer move forward."""

    def run(
        self,
        *,
        intention: SaleProviderIntention,
        reason: SaleProviderIntention.WithdrawReason,
        notes: str | None = None,
    ) -> SaleProviderIntention:
        intention.withdraw(reason=reason, notes=notes)
        update_fields = ["state", "withdraw_reason", "updated_at"]
        if notes:
            update_fields.append("documentation_notes")
        intention.save(update_fields=update_fields)
        return intention


class PromoteSaleProviderIntentionService(BaseService):
    """Promote a provider intention into a fully managed opportunity."""

    def run(
        self,
        *,
        intention: SaleProviderIntention,
        opportunity_notes: str | None = None,
        marketing_package_data: Mapping[str, Any] | None = None,
        tokkobroker_property: TokkobrokerProperty | None = None,
    ):
        if not intention.is_promotable():
            raise ValidationError(
                "Intention must be valuated and not converted before promotion."
            )

        opportunity = CreateOpportunityService.call(
            intention=intention,
            notes=opportunity_notes,
            marketing_package_data=marketing_package_data,
            tokkobroker_property=tokkobroker_property,
        )

        intention.mark_converted(opportunity=opportunity)
        intention.save(
            update_fields=[
                "state",
                "converted_at",
                "updated_at",
            ]
        )
        return opportunity


__all__ = [
    "CreateSaleProviderIntentionService",
    "DeliverSaleValuationService",
    "WithdrawSaleProviderIntentionService",
    "PromoteSaleProviderIntentionService",
]
