from typing import Any, Mapping, Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import MarketingPackage, Opportunity, Operation, Validation
from core.services.marketing import MarketingPackageActivateService
from core.services.base import BaseService


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


class OpportunityTransitionService(BaseService):
    state_required: Opportunity.State
    state_target: Opportunity.State

    def ensure_state(self, opportunity: Opportunity) -> None:
        if opportunity.state != self.state_required:
            raise ValidationError(
                f"Opportunity must be in '{self.state_required}' state; current state is '{opportunity.state}'."
            )

    def transition(self, opportunity: Opportunity, *, actor: Optional[Any] = None) -> Opportunity:
        self.ensure_state(opportunity)
        opportunity.state = self.state_target
        opportunity.save(update_fields=["state", "updated_at"])
        return opportunity


class OpportunityValidateService(OpportunityTransitionService):
    state_required = Opportunity.State.CAPTURING
    state_target = Opportunity.State.VALIDATING

    def run(self, *, opportunity: Opportunity, actor: Optional[Any] = None) -> Opportunity:
        opportunity = self.transition(opportunity, actor=actor)
        Validation.objects.get_or_create(opportunity=opportunity)
        return opportunity


class OpportunityPublishService(OpportunityTransitionService):
    state_required = Opportunity.State.VALIDATING
    state_target = Opportunity.State.MARKETING

    def run(self, *, opportunity: Opportunity, actor: Optional[Any] = None) -> Opportunity:
        if not opportunity.validations.filter(state=Validation.State.ACCEPTED).exists():
            raise ValidationError("Opportunity cannot be published without an accepted validation.")

        opportunity = self.transition(opportunity, actor=actor)
        latest_package = opportunity.marketing_packages.order_by("-created_at").first()
        if latest_package and latest_package.state == MarketingPackage.State.PREPARING:
            MarketingPackageActivateService.call(package=latest_package)
        return opportunity


class OpportunityCloseService(OpportunityTransitionService):
    state_required = Opportunity.State.MARKETING
    state_target = Opportunity.State.CLOSED

    def run(self, *, opportunity: Opportunity, actor: Optional[Any] = None) -> Opportunity:
        if not opportunity.operations.filter(state=Operation.State.CLOSED).exists():
            raise ValidationError("Opportunity cannot be closed without a closed operation.")
        return self.transition(opportunity, actor=actor)
