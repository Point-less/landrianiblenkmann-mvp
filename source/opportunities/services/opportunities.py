from typing import Any, Mapping, Optional

from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from integrations.models import TokkobrokerProperty
from opportunities.models import (
    MarketingPackage,
    ProviderOpportunity,
    SeekerOpportunity,
    Validation,
)
from intentions.models import ProviderIntention, SeekerIntention

from utils.services import BaseService
from utils.authorization import (
    PROVIDER_OPPORTUNITY_CREATE,
    PROVIDER_OPPORTUNITY_PUBLISH,
    PROVIDER_OPPORTUNITY_CLOSE,
    SEEKER_OPPORTUNITY_CREATE,
)


class CreateOpportunityService(BaseService):
    """Create a provider opportunity with an optional initial marketing package."""

    required_action = PROVIDER_OPPORTUNITY_CREATE

    def run(
        self,
        *,
        intention: ProviderIntention,
        notes: str | None = None,
        gross_commission_pct,
        marketing_package_data: Mapping[str, Any] | None = None,
        tokkobroker_property: TokkobrokerProperty,
        listing_kind=ProviderOpportunity.ListingKind.EXCLUSIVE,
        contract_expires_on=None,
        contract_effective_on=None,
        valuation_test_value=None,
        valuation_close_value=None,
    ) -> ProviderOpportunity:
        marketing_payload = dict(marketing_package_data or {})

        if self.s.opportunities.ProviderOpportunityByTokkobrokerPropertyQuery(
            tokkobroker_property=tokkobroker_property
        ).exists():
            raise ValidationError("Tokkobroker property is already linked to another opportunity.")

        opportunity = ProviderOpportunity.objects.create(
            source_intention=intention,
            notes=notes or intention.notes,
            tokkobroker_property=tokkobroker_property,
            gross_commission_pct=gross_commission_pct,
            listing_kind=listing_kind or ProviderOpportunity.ListingKind.EXCLUSIVE,
            contract_expires_on=contract_expires_on,
            contract_effective_on=contract_effective_on,
            valuation_test_value=valuation_test_value if valuation_test_value is not None else getattr(intention.valuation, "test_value", 0),
            valuation_close_value=valuation_close_value if valuation_close_value is not None else getattr(intention.valuation, "close_value", 0),
        )

        marketing_payload.setdefault("headline", f"Listing for {intention.property}")

        MarketingPackage.objects.create(
            opportunity=opportunity,
            **marketing_payload,
        )

        Validation.objects.create(opportunity=opportunity)

        return opportunity


class OpportunityPublishService(BaseService):
    def run(self, *, opportunity: ProviderOpportunity, actor: Optional[Any] = None) -> ProviderOpportunity:
        try:
            opportunity.start_marketing()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        opportunity.save(update_fields=["state", "updated_at"])
        return opportunity

    required_action = PROVIDER_OPPORTUNITY_PUBLISH


class OpportunityCloseService(BaseService):
    def run(self, *, opportunity: ProviderOpportunity, actor: Optional[Any] = None) -> ProviderOpportunity:
        try:
            opportunity.close_opportunity()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        opportunity.save(update_fields=["state", "updated_at"])
        return opportunity

    required_action = PROVIDER_OPPORTUNITY_CLOSE


class CreateSeekerOpportunityService(BaseService):
    """Convert a seeker intention into an actionable opportunity."""

    required_action = SEEKER_OPPORTUNITY_CREATE

    def run(
        self,
        *,
        intention: SeekerIntention,
        notes: str | None = None,
        gross_commission_pct,
    ) -> SeekerOpportunity:
        try:
            _ = intention.seeker_opportunity
        except SeekerOpportunity.DoesNotExist:
            pass
        else:
            raise ValidationError("Intention already has a seeker opportunity attached.")
        if intention.state != SeekerIntention.State.QUALIFYING:
            raise ValidationError("Seeker intention must be qualifying before conversion.")

        opportunity = SeekerOpportunity.objects.create(
            source_intention=intention,
            notes=notes or intention.notes,
            gross_commission_pct=gross_commission_pct,
        )

        intention.mark_converted(opportunity=opportunity)
        intention.save(update_fields=["state", "updated_at"])
        return opportunity
