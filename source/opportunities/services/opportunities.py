from typing import Any, Mapping, Optional

from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from opportunities.models import (
    MarketingPackage,
    ProviderOpportunity,
    SeekerOpportunity,
    Validation,
)
from intentions.models import SaleProviderIntention, SaleSeekerIntention

from utils.services import BaseService
from .marketing import MarketingPackageActivateService


class CreateOpportunityService(BaseService):
    """Create a provider opportunity with an optional initial marketing package."""

    def run(
        self,
        *,
        intention: SaleProviderIntention,
        notes: str | None = None,
        marketing_package_data: Mapping[str, Any] | None = None,
    ) -> ProviderOpportunity:
        marketing_payload = dict(marketing_package_data or {})
        opportunity = ProviderOpportunity.objects.create(
            source_intention=intention,
            notes=notes or intention.documentation_notes,
        )

        marketing_payload.setdefault("headline", f"Listing for {intention.property}")

        MarketingPackage.objects.create(
            opportunity=opportunity,
            **marketing_payload,
        )

        Validation.objects.create(opportunity=opportunity)

        return opportunity


class OpportunityValidateService(BaseService):
    def run(self, *, opportunity: ProviderOpportunity, actor: Optional[Any] = None) -> ProviderOpportunity:
        try:
            opportunity.start_validation()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        opportunity.save(update_fields=["state", "updated_at"])
        Validation.objects.get_or_create(opportunity=opportunity)
        return opportunity


class OpportunityPublishService(BaseService):
    def run(self, *, opportunity: ProviderOpportunity, actor: Optional[Any] = None) -> ProviderOpportunity:
        try:
            opportunity.start_marketing()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        opportunity.save(update_fields=["state", "updated_at"])
        latest_package = opportunity.marketing_packages.order_by("-created_at").first()
        if latest_package and latest_package.state == MarketingPackage.State.PREPARING:
            MarketingPackageActivateService.call(package=latest_package)
        return opportunity


class OpportunityCloseService(BaseService):
    def run(self, *, opportunity: ProviderOpportunity, actor: Optional[Any] = None) -> ProviderOpportunity:
        try:
            opportunity.close_opportunity()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        opportunity.save(update_fields=["state", "updated_at"])
        return opportunity


class CreateSeekerOpportunityService(BaseService):
    """Convert a seeker intention into an actionable opportunity."""

    def run(
        self,
        *,
        intention: SaleSeekerIntention,
        notes: str | None = None,
    ) -> SeekerOpportunity:
        if hasattr(intention, "seeker_opportunity"):
            raise ValidationError("Intention already has a seeker opportunity attached.")
        if intention.state != SaleSeekerIntention.State.MANDATED:
            raise ValidationError("Seeker intention must be mandated before conversion.")

        opportunity = SeekerOpportunity.objects.create(
            source_intention=intention,
            notes=notes or intention.notes,
        )

        intention.mark_converted(opportunity=opportunity)
        intention.save(update_fields=["state", "updated_at"])
        return opportunity
