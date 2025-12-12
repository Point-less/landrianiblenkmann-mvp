from typing import Optional

from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from opportunities.models import ProviderOpportunity, Validation

from utils.services import BaseService


class ValidationPresentService(BaseService):
    """Mark a validation as presented."""

    def run(self, *, validation: Validation, reviewer=None) -> Validation:
        # reviewer is accepted for compatibility with callers/tests; currently unused.
        validation.ensure_required_documents_uploaded()
        try:
            validation.present()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        validation.save(update_fields=["state", "presented_at", "updated_at"])
        return validation


class ValidationRejectService(BaseService):
    """Return a presented validation back to preparation."""

    def run(self, *, validation: Validation, notes: Optional[str] = None) -> Validation:
        try:
            validation.revoke(notes=notes)
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        update_fields = ["state", "validated_at", "updated_at"]
        if notes is not None:
            update_fields.append("notes")
        validation.save(update_fields=update_fields)
        return validation


class ValidationAcceptService(BaseService):
    """Approve a presented validation and advance the opportunity."""

    def run(self, *, validation: Validation) -> Validation:
        validation.ensure_documents_ready_for_acceptance()
        try:
            validation.approve()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        validation.save(update_fields=["state", "validated_at", "updated_at"])

        opportunity = validation.opportunity
        if opportunity.state == ProviderOpportunity.State.VALIDATING:
            self.s.opportunities.OpportunityPublishService(opportunity=opportunity)
        return validation


class ValidationEnsureService(BaseService):
    """Ensure a Validation record exists for the given provider opportunity."""

    atomic = False

    def run(self, *, opportunity):
        validation, _ = Validation.objects.get_or_create(opportunity=opportunity)
        return validation


__all__ = [
    "ValidationPresentService",
    "ValidationRejectService",
    "ValidationAcceptService",
    "ValidationEnsureService",
]
