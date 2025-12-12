"""Provider-facing services for intentions."""

from typing import Any, Mapping

from django.core.exceptions import ValidationError

from core.models import Agent, Contact, Currency, Property
from integrations.models import TokkobrokerProperty
from intentions.models import ProviderIntention, Valuation
from opportunities.services import CreateOpportunityService
from utils.services import BaseService
from utils.authorization import (
    PROVIDER_INTENTION_CREATE,
    PROVIDER_INTENTION_VALUATE,
    PROVIDER_INTENTION_WITHDRAW,
    PROVIDER_INTENTION_PROMOTE,
)


class CreateProviderIntentionService(BaseService):
    """Register a new provider intention before it becomes an opportunity."""

    required_action = PROVIDER_INTENTION_CREATE

    def run(
        self,
        *,
        owner: Contact,
        agent: Agent,
        property: Property,
        operation_type,
        notes: str | None = None,
    ) -> ProviderIntention:
        existing = ProviderIntention.objects.filter(
            agent=agent,
            property=property,
        ).exclude(
            state__in=[
                ProviderIntention.State.CONVERTED,
                ProviderIntention.State.WITHDRAWN,
            ]
        )
        if existing.exists():
            raise ValidationError(
                "An active provider intention already exists for this property and agent."
            )
        return ProviderIntention.objects.create(
            owner=owner,
            agent=agent,
            property=property,
            operation_type=operation_type,
            notes=notes or "",
        )


class DeliverValuationService(BaseService):
    """Attach a valuation and advance the provider intention FSM."""

    required_action = PROVIDER_INTENTION_VALUATE

    def run(
        self,
        *,
        intention: ProviderIntention,
        amount,
        currency: Currency,
        notes: str | None = None,
        valuation_date=None,
        test_value,
        close_value,
    ) -> Valuation:
        intention.deliver_valuation(
            amount=amount,
            currency=currency,
            notes=notes,
            valuation_date=valuation_date,
            test_value=test_value,
            close_value=close_value,
        )
        intention.save(update_fields=["state", "valuation", "updated_at"])
        return intention.valuation  # type: ignore[return-value]


class WithdrawProviderIntentionService(BaseService):
    """Withdraw an intention that will no longer move forward."""

    required_action = PROVIDER_INTENTION_WITHDRAW

    def run(
        self,
        *,
        intention: ProviderIntention,
        reason: ProviderIntention.WithdrawReason,
        notes: str | None = None,
    ) -> ProviderIntention:
        intention.withdraw(reason=reason, notes=notes)
        update_fields = ["state", "withdraw_reason", "updated_at"]
        if notes:
            update_fields.append("notes")
        intention.save(update_fields=update_fields)
        return intention


class PromoteProviderIntentionService(BaseService):
    """Promote a provider intention into a fully managed opportunity."""

    required_action = PROVIDER_INTENTION_PROMOTE

    def run(
        self,
        *,
        intention: ProviderIntention,
        notes: str | None = None,
        gross_commission_pct,
        marketing_package_data: Mapping[str, Any] | None = None,
        tokkobroker_property: TokkobrokerProperty,
        listing_kind=None,
        contract_expires_on=None,
        contract_effective_on=None,
        valuation_test_value=None,
        valuation_close_value=None,
    ):
        if not intention.is_promotable():
            raise ValidationError(
                "Intention must be valuated and not converted before promotion."
            )
        if not tokkobroker_property:
            raise ValidationError("Tokkobroker property is required to promote the intention.")

        opportunity = CreateOpportunityService.call(
            intention=intention,
            notes=notes,
            gross_commission_pct=gross_commission_pct,
            marketing_package_data=marketing_package_data,
            tokkobroker_property=tokkobroker_property,
            listing_kind=listing_kind,
            contract_expires_on=contract_expires_on,
            contract_effective_on=contract_effective_on,
            valuation_test_value=valuation_test_value,
            valuation_close_value=valuation_close_value,
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
    "CreateProviderIntentionService",
    "DeliverValuationService",
    "WithdrawProviderIntentionService",
    "PromoteProviderIntentionService",
]
