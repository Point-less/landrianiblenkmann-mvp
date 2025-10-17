from django.core.exceptions import ValidationError

from opportunities.models import MarketingPackage, Validation

from .base import BaseService


class MarketingPackageBaseService(BaseService):
    def ensure_state(self, package: MarketingPackage, expected: MarketingPackage.State) -> None:
        if package.state != expected:
            raise ValidationError(
                f"Marketing package must be in '{expected}' state; current state is '{package.state}'."
            )


class MarketingPackageActivateService(MarketingPackageBaseService):
    """Move a package from preparing to available."""

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        self.ensure_state(package, MarketingPackage.State.PREPARING)
        return package.clone(state=MarketingPackage.State.AVAILABLE)


class MarketingPackageReserveService(MarketingPackageBaseService):
    """Reserve an available package (available -> paused)."""

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        self.ensure_state(package, MarketingPackage.State.AVAILABLE)
        opportunity = package.opportunity
        if not opportunity.validations.filter(state=Validation.State.ACCEPTED).exists():
            raise ValidationError("Cannot reserve marketing package before validation is accepted.")
        return package.clone(state=MarketingPackage.State.PAUSED)


class MarketingPackageReleaseService(MarketingPackageBaseService):
    """Release a paused package back to available."""

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        self.ensure_state(package, MarketingPackage.State.PAUSED)
        return package.clone(state=MarketingPackage.State.AVAILABLE)
