from typing import Optional

from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from core.models import Currency
from opportunities.models import MarketingPackage, Operation, ProviderOpportunity, SeekerOpportunity
from opportunities.services.marketing import MarketingPackagePauseService

from utils.services import BaseService


class CreateOperationService(BaseService):
    """Start an operation linking a provider and seeker opportunity."""

    active_states = (Operation.State.OFFERED, Operation.State.REINFORCED)

    def run(
        self,
        *,
        provider_opportunity: ProviderOpportunity,
        seeker_opportunity: SeekerOpportunity,
        offered_amount=None,
        reserve_amount=None,
        reinforcement_amount=None,
        currency: Currency | None = None,
        notes: str | None = None,
    ) -> Operation:
        if provider_opportunity.state != ProviderOpportunity.State.MARKETING:
            raise ValidationError({
                "provider_opportunity": "Provider opportunity must be marketing before opening an operation.",
            })
        if seeker_opportunity.state not in {
            SeekerOpportunity.State.MATCHING,
            SeekerOpportunity.State.NEGOTIATING,
        }:
            raise ValidationError({
                "seeker_opportunity": "Seeker opportunity must be matching or negotiating.",
            })

        if Operation.objects.filter(
            provider_opportunity=provider_opportunity,
            seeker_opportunity=seeker_opportunity,
            state__in=self.active_states,
        ).exists():
            raise ValidationError("An active operation already exists for this pair.")

        operation = Operation.objects.create(
            provider_opportunity=provider_opportunity,
            seeker_opportunity=seeker_opportunity,
            offered_amount=offered_amount,
            reserve_amount=reserve_amount,
            reinforcement_amount=reinforcement_amount,
            currency=currency,
            notes=notes or "",
        )

        self._reserve_marketing_packages(provider_opportunity)

        if seeker_opportunity.state == SeekerOpportunity.State.MATCHING:
            try:
                seeker_opportunity.start_negotiation()
            except TransitionNotAllowed as exc:
                raise ValidationError(str(exc)) from exc
            seeker_opportunity.save(update_fields=["state", "updated_at"])

        return operation

    def _reserve_marketing_packages(self, provider_opportunity: ProviderOpportunity) -> None:
        packages = provider_opportunity.marketing_packages.filter(
            state=MarketingPackage.State.AVAILABLE
        ).order_by('-created_at')
        for package in packages:
            try:
                MarketingPackagePauseService.call(package=package)
            except ValidationError:
                continue


class OperationReinforceService(BaseService):
    """Transition an offered operation into reinforced."""

    def run(self, *, operation: Operation) -> Operation:
        try:
            operation.reinforce()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        operation.save(update_fields=["state", "occurred_at", "updated_at"])
        return operation


class OperationCloseService(BaseService):
    """Close a reinforced operation and update linked opportunities."""

    def run(self, *, operation: Operation, opportunity=None) -> Operation:  # opportunity kept for backward compat
        try:
            operation.close()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        return operation


class OperationLoseService(BaseService):
    """Mark a reinforced operation as lost (closed outcome)."""

    def run(self, *, operation: Operation, lost_reason: Optional[str] = None) -> Operation:
        try:
            operation.lose(reason=lost_reason)
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive
            raise ValidationError(str(exc)) from exc

        operation.save(update_fields=["state", "occurred_at", "lost_reason", "updated_at"])
        return operation
