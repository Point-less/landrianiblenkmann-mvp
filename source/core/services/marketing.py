from django.core.exceptions import ValidationError

from core.models import MarketingPackage
from core.services.base import BaseService


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
        package.state = MarketingPackage.State.AVAILABLE
        package.save(update_fields=["state", "updated_at"])
        return package


class MarketingPackageReserveService(MarketingPackageBaseService):
    """Reserve an available package (available -> paused)."""

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        self.ensure_state(package, MarketingPackage.State.AVAILABLE)
        package.state = MarketingPackage.State.PAUSED
        package.save(update_fields=["state", "updated_at"])
        return package


class MarketingPackageReleaseService(MarketingPackageBaseService):
    """Release a paused package back to available."""

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        self.ensure_state(package, MarketingPackage.State.PAUSED)
        package.state = MarketingPackage.State.AVAILABLE
        package.save(update_fields=["state", "updated_at"])
        return package
