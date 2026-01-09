from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from opportunities.models import MarketingPackage, ProviderOpportunity

from utils.services import BaseService
from utils.authorization import PROVIDER_OPPORTUNITY_PUBLISH


class MarketingPackageActivateService(BaseService):
    """Move a package from preparing to available."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        try:
            new_package = package.activate()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        new_package.snapshot_revision()
        return new_package


class MarketingPackageReleaseService(BaseService):
    """Release a paused package back to available."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        try:
            new_package = package.publish()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        new_package.snapshot_revision()
        return new_package


class MarketingPackageCreateService(BaseService):
    """Create a new marketing package for an opportunity in marketing stage."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, opportunity: ProviderOpportunity, **attrs) -> MarketingPackage:
        if opportunity.state != ProviderOpportunity.State.MARKETING:
            raise ValidationError("Opportunity must be in marketing stage to add packages.")
        package = MarketingPackage.objects.create(opportunity=opportunity, **attrs)
        package.snapshot_revision()
        return package


class MarketingPackageUpdateService(BaseService):
    """Update editable fields on a marketing package."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, package: MarketingPackage, **attrs) -> MarketingPackage:
        updatable = {key: value for key, value in attrs.items() if key in {
            'headline',
            'description',
            'price',
            'currency',
            'features',
            'media_assets',
        }}
        for field, value in updatable.items():
            setattr(package, field, value)
        if not updatable:
            return package
        package.save(update_fields=[*updatable.keys(), 'updated_at'])
        package.snapshot_revision()
        return package


class MarketingPackagePauseService(BaseService):
    """Pause an available package (available -> paused)."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        try:
            new_package = package.pause()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        new_package.snapshot_revision()
        return new_package
