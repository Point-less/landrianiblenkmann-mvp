from typing import Optional

from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from core.models import Currency
from opportunities.models import Operation, OperationAgreement, ProviderOpportunity, SeekerOpportunity
from utils.services import BaseService


class CreateOperationAgreementService(BaseService):
    """Create a new operation agreement between provider and seeker opportunities."""

    def run(
        self,
        *,
        provider_opportunity: ProviderOpportunity,
        seeker_opportunity: SeekerOpportunity,
        notes: str | None = None,
    ) -> OperationAgreement:
        """Create a new agreement in PENDING state with validations."""
        agreement = OperationAgreement(
            provider_opportunity=provider_opportunity,
            seeker_opportunity=seeker_opportunity,
            notes=notes or "",
        )
        
        agreement.validate_operation_types_match()
        agreement.validate_opportunity_states()
        
        # Check for existing active agreements
        existing = OperationAgreement.objects.filter(
            provider_opportunity=provider_opportunity,
            seeker_opportunity=seeker_opportunity,
            state__in=[OperationAgreement.State.PENDING, OperationAgreement.State.AGREED],
        ).exists()
        
        if existing:
            raise ValidationError("An active agreement already exists for this opportunity pair.")
        
        # Check for existing active operations
        existing_operations = Operation.objects.filter(
            agreement__provider_opportunity=provider_opportunity,
            agreement__seeker_opportunity=seeker_opportunity,
            state__in=[Operation.State.OFFERED, Operation.State.REINFORCED],
        ).exists()
        
        if existing_operations:
            raise ValidationError("An active operation already exists for this opportunity pair.")
        
        agreement.save()
        return agreement


class AgreeOperationAgreementService(BaseService):
    """Transition an agreement from PENDING to AGREED state."""

    def run(self, *, agreement: OperationAgreement) -> OperationAgreement:
        try:
            agreement.agree()
        except TransitionNotAllowed as exc:
            raise ValidationError(str(exc)) from exc
        
        agreement.save(update_fields=["state", "agreed_at", "updated_at"])
        return agreement


class SignOperationAgreementService(BaseService):
    """Sign an agreement and automatically create the corresponding operation."""

    def run(
        self,
        *,
        agreement: OperationAgreement,
        signed_document,
        initial_offered_amount,
        reserve_amount,
        reserve_deadline,
        currency: Currency,
        notes: str | None = None,
    ) -> tuple[OperationAgreement, Operation]:
        """Sign the agreement and create the operation automatically."""
        try:
            agreement.sign()
        except TransitionNotAllowed as exc:
            raise ValidationError(str(exc)) from exc
        
        agreement.save(update_fields=["state", "signed_at", "updated_at"])
        
        # Create the operation using the existing CreateOperationService
        operation = self.s.opportunities.CreateOperationService(
            agreement=agreement,
            signed_document=signed_document,
            initial_offered_amount=initial_offered_amount,
            reserve_amount=reserve_amount,
            reserve_deadline=reserve_deadline,
            currency=currency,
            notes=notes,
        )
        
        return agreement, operation


class RevokeOperationAgreementService(BaseService):
    """Revoke an agreement back to PENDING state."""

    def run(self, *, agreement: OperationAgreement) -> OperationAgreement:
        if agreement.state == OperationAgreement.State.SIGNED:
            raise ValidationError("Cannot revoke a signed agreement. The operation has already been created.")
        
        try:
            agreement.revoke()
        except TransitionNotAllowed as exc:
            raise ValidationError(str(exc)) from exc
        
        agreement.save(update_fields=["state", "agreed_at", "updated_at"])
        return agreement


class CancelOperationAgreementService(BaseService):
    """Cancel an agreement from PENDING or AGREED state."""

    def run(self, *, agreement: OperationAgreement, reason: str | None = None) -> OperationAgreement:
        if agreement.state == OperationAgreement.State.SIGNED:
            raise ValidationError("Cannot cancel a signed agreement. The operation has already been created.")
        
        try:
            agreement.cancel(reason=reason)
        except TransitionNotAllowed as exc:
            raise ValidationError(str(exc)) from exc
        
        agreement.save(update_fields=["state", "cancelled_at", "cancellation_reason", "updated_at"])
        return agreement
