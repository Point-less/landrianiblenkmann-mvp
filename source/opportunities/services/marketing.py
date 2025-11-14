from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from opportunities.models import MarketingPackage, ProviderOpportunity

from utils.services import BaseService


class MarketingPackageActivateService(BaseService):
    """Move a package from preparing to available."""

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        try:
            new_package = package.activate()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        return new_package


class MarketingPackageReleaseService(BaseService):
    """Release a paused package back to available."""

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        try:
            new_package = package.release()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        return new_package


class MarketingPackageCreateService(BaseService):
    """Create a new marketing package for an opportunity in marketing stage."""

    def run(self, *, opportunity: ProviderOpportunity, **attrs) -> MarketingPackage:
        if opportunity.state != ProviderOpportunity.State.MARKETING:
            raise ValidationError("Opportunity must be in marketing stage to add packages.")
        package = MarketingPackage.objects.create(opportunity=opportunity, **attrs)
        return package


class MarketingPackageUpdateService(BaseService):
    """Update editable fields on a marketing package."""

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
        return package


class MarketingPackagePauseService(BaseService):
    """Pause an available package (available -> paused)."""

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        try:
            new_package = package.reserve()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        return new_package
