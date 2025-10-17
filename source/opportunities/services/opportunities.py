from typing import Any, Mapping, Optional

from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from opportunities.models import MarketingPackage, Opportunity, Validation

from utils.services import BaseService
from .marketing import MarketingPackageActivateService


class CreateOpportunityService(BaseService):
    """Create an opportunity with an optional initial marketing package."""

    def run(
        self,
        *,
        opportunity_data: Mapping[str, Any],
        marketing_package_data: Mapping[str, Any] | None = None,
    ) -> Opportunity:
        marketing_payload = dict(marketing_package_data or {})
        opportunity = Opportunity.objects.create(**opportunity_data)

        marketing_payload.setdefault("headline", opportunity.title)

        MarketingPackage.objects.create(
            opportunity=opportunity,
            **marketing_payload,
        )

        Validation.objects.create(opportunity=opportunity)

        return opportunity


class OpportunityValidateService(BaseService):
    def run(self, *, opportunity: Opportunity, actor: Optional[Any] = None) -> Opportunity:
        try:
            opportunity.start_validation()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        opportunity.save(update_fields=["state", "updated_at"])
        Validation.objects.get_or_create(opportunity=opportunity)
        return opportunity


class OpportunityPublishService(BaseService):
    def run(self, *, opportunity: Opportunity, actor: Optional[Any] = None) -> Opportunity:
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
    def run(self, *, opportunity: Opportunity, actor: Optional[Any] = None) -> Opportunity:
        try:
            opportunity.close_opportunity()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        opportunity.save(update_fields=["state", "updated_at"])
        return opportunity
