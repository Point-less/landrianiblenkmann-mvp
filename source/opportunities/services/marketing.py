from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from opportunities.models import MarketingPackage

from .base import BaseService


class MarketingPackageActivateService(BaseService):
    """Move a package from preparing to available."""

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        try:
            new_package = package.activate()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        return new_package


class MarketingPackageReserveService(BaseService):
    """Reserve an available package (available -> paused)."""

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        try:
            new_package = package.reserve()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        except ValidationError:
            raise
        return new_package


class MarketingPackageReleaseService(BaseService):
    """Release a paused package back to available."""

    def run(self, *, package: MarketingPackage) -> MarketingPackage:
        try:
            new_package = package.release()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc
        return new_package
