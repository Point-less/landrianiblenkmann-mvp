from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from opportunities.models import MarketingPackage, ProviderOpportunity

from utils.services import BaseService
from utils.authorization import PROVIDER_OPPORTUNITY_PUBLISH


class MarketingPackageActivateService(BaseService):
    """Move a package from preparing to available."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        if not package.is_active:
            raise ValidationError("Cannot transition an inactive marketing package revision.")
        try:
            new_package = package.activate()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        return new_package


class MarketingPackageReleaseService(BaseService):
    """Release a paused package back to available."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        if package.opportunity.state == ProviderOpportunity.State.CLOSED:
            raise ValidationError("Cannot resume a marketing package for a closed opportunity.")
        if not package.is_active:
            raise ValidationError("Cannot transition an inactive marketing package revision.")
        try:
            new_package = package.publish()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        return new_package


class MarketingPackageCreateService(BaseService):
    """Create a new marketing package for an opportunity in marketing stage."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, opportunity: ProviderOpportunity, **attrs) -> MarketingPackage:
        if opportunity.state != ProviderOpportunity.State.MARKETING:
            raise ValidationError("Opportunity must be in marketing stage to add packages.")
        return MarketingPackage.objects.create(opportunity=opportunity, **attrs)


class MarketingPackageUpdateService(BaseService):
    """Update editable fields on a marketing package."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, package: MarketingPackage, **attrs) -> MarketingPackage:
        if not package.is_active:
            raise ValidationError("Cannot edit an inactive marketing package revision.")
        updatable = {key: value for key, value in attrs.items() if key in {
            'headline',
            'description',
            'price',
            'currency',
            'features',
            'media_assets',
        }}
        if not updatable:
            return package
        return package.clone_as_revision(**updatable)


class MarketingPackagePauseService(BaseService):
    """Pause an available package (available -> paused)."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        if not package.is_active:
            raise ValidationError("Cannot transition an inactive marketing package revision.")
        try:
            new_package = package.pause()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        return new_package
