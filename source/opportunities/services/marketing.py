from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from opportunities.models import MarketingPackage, MarketingPublication, ProviderOpportunity

from utils.services import BaseService
from utils.authorization import PROVIDER_OPPORTUNITY_PUBLISH


class MarketingPackageActivateService(BaseService):
    """Move a package from preparing to available."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, package: MarketingPackage) -> MarketingPublication:
        if not package.is_active:
            raise ValidationError("Cannot transition an inactive marketing package revision.")
        publication, _ = MarketingPublication.objects.get_or_create(
            opportunity=package.opportunity,
            defaults={"package": package},
        )
        if publication.package_id != package.pk:
            publication.package = package
            publication.save(update_fields=["package", "updated_at"])
        try:
            updated_publication = publication.activate()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        return updated_publication


class MarketingPackageReleaseService(BaseService):
    """Release a paused package back to available."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, package: MarketingPackage) -> MarketingPublication:
        if package.opportunity.state == ProviderOpportunity.State.CLOSED:
            raise ValidationError("Cannot resume a marketing package for a closed opportunity.")
        if not package.is_active:
            raise ValidationError("Cannot transition an inactive marketing package revision.")
        publication = MarketingPublication.objects.filter(opportunity=package.opportunity).first()
        if not publication:
            raise ValidationError("No publication configured for this marketing package.")
        if publication.package_id != package.pk:
            publication.package = package
            publication.save(update_fields=["package", "updated_at"])
        try:
            updated_publication = publication.publish()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        return updated_publication


class MarketingPackageCreateService(BaseService):
    """Create a new marketing package for an opportunity in marketing stage."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, opportunity: ProviderOpportunity, **attrs) -> MarketingPackage:
        if opportunity.state not in (ProviderOpportunity.State.MARKETING, ProviderOpportunity.State.VALIDATING):
            raise ValidationError("Opportunity must be in marketing or validating stage to add packages.")
        package = MarketingPackage.objects.create(opportunity=opportunity, **attrs)
        MarketingPublication.objects.update_or_create(
            opportunity=opportunity,
            defaults={"package": package},
        )
        return package


class MarketingPackageUpdateService(BaseService):
    """Update editable fields on a marketing package."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, package: MarketingPackage, **attrs) -> MarketingPackage:
        if package.opportunity.state != ProviderOpportunity.State.MARKETING:
            raise ValidationError("Cannot edit marketing packages outside marketing stage.")
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
        # Skip creating a new revision when nothing actually changed
        changed = {}
        for field, value in updatable.items():
            if getattr(package, field) != value:
                changed[field] = value

        if not changed:
            return package

        new_package = package.clone_as_revision(**changed)
        MarketingPublication.objects.update_or_create(
            opportunity=package.opportunity,
            defaults={"package": new_package},
        )
        return new_package


class MarketingPackagePauseService(BaseService):
    """Pause an available package (available -> paused)."""

    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, package: MarketingPackage) -> MarketingPublication:
        if not package.is_active:
            raise ValidationError("Cannot transition an inactive marketing package revision.")
        publication = MarketingPublication.objects.filter(opportunity=package.opportunity).first()
        if not publication:
            raise ValidationError("No publication configured for this marketing package.")
        if publication.package_id != package.pk:
            publication.package = package
            publication.save(update_fields=["package", "updated_at"])
        try:
            updated_publication = publication.pause()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        return updated_publication
