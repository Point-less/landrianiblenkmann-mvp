from typing import Optional

from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from core.models import Currency
from opportunities.models import MarketingPackage, Operation, ProviderOpportunity, SeekerOpportunity
from opportunities.services.marketing import MarketingPackagePauseService
from opportunities.services.queries import (
    ActiveOperationsBetweenOpportunitiesQuery,
    SeekerActiveOperationsQuery,
)

from utils.services import BaseService
from utils.authorization import (
    OPERATION_CREATE,
    OPERATION_REINFORCE,
    OPERATION_CLOSE,
    OPERATION_LOSE,
)


class CreateOperationService(BaseService):
    """Start an operation linking a provider and seeker opportunity."""

    required_action = OPERATION_CREATE

    active_states = (Operation.State.OFFERED, Operation.State.REINFORCED)

    def run(
        self,
        *,
        agreement,
        signed_document,
        reserve_amount,
        reserve_deadline,
        initial_offered_amount=None,
        currency: Currency | None = None,
        notes: str | None = None,
    ) -> Operation:
        provider_opportunity = agreement.provider_opportunity
        seeker_opportunity = agreement.seeker_opportunity

        if self.s.opportunities.ActiveOperationsBetweenOpportunitiesQuery(
            provider_opportunity=provider_opportunity,
            seeker_opportunity=seeker_opportunity,
        ).exists():
            raise ValidationError("An active operation already exists for this pair.")

        if reserve_amount is None:
            raise ValidationError({"reserve_amount": "Reserve amount is required."})
        if reserve_deadline is None:
            raise ValidationError({"reserve_deadline": "Reserve deadline is required."})

        operation = Operation.objects.create(
            agreement=agreement,
            signed_document=signed_document,
            initial_offered_amount=initial_offered_amount,
            offered_amount=None,
            reserve_amount=reserve_amount,
            reserve_deadline=reserve_deadline,
            reinforcement_amount=None,
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
            state=MarketingPackage.State.PUBLISHED
        ).order_by('-created_at')
        for package in packages:
            try:
                self.s.opportunities.MarketingPackagePauseService(package=package)
            except ValidationError:
                continue


class OperationReinforceService(BaseService):
    """Transition an offered operation into reinforced."""

    required_action = OPERATION_REINFORCE

    def run(self, *, operation: Operation, offered_amount=None, reinforcement_amount=None, declared_deed_value=None) -> Operation:
        try:
            operation.reinforce()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        # Prefill offered_amount with initial if none provided
        if offered_amount is None:
            offered_amount = operation.initial_offered_amount
        operation.offered_amount = offered_amount
        if reinforcement_amount is not None:
            operation.reinforcement_amount = reinforcement_amount
        if declared_deed_value is not None:
            operation.declared_deed_value = declared_deed_value

        operation.save(update_fields=["state", "occurred_at", "offered_amount", "reinforcement_amount", "declared_deed_value", "updated_at"])
        return operation


class OperationCloseService(BaseService):
    """Close a reinforced operation and update linked opportunities."""

    required_action = OPERATION_CLOSE

    def run(self, *, operation: Operation, opportunity=None) -> Operation:  # opportunity kept for backward compat
        try:
            operation.close()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        return operation


class OperationLoseService(BaseService):
    """Mark a reinforced operation as lost (closed outcome)."""

    required_action = OPERATION_LOSE

    def run(self, *, operation: Operation, lost_reason: Optional[str] = None) -> Operation:
        try:
            operation.lose(reason=lost_reason)
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive
            raise ValidationError(str(exc)) from exc

        operation.save(update_fields=["state", "occurred_at", "lost_reason", "updated_at"])

        seeker = operation.seeker_opportunity
        has_other_active = self.s.opportunities.SeekerActiveOperationsQuery(seeker_opportunity=seeker).exclude(pk=operation.pk).exists()

        if seeker.state == SeekerOpportunity.State.NEGOTIATING and not has_other_active:
            try:
                seeker.resume_matching()
            except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
                raise ValidationError(str(exc)) from exc

            seeker.save(update_fields=["state", "updated_at"])
        return operation
