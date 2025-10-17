from typing import Optional

from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from opportunities.models import Opportunity, Validation

from .base import BaseService
from .opportunities import OpportunityPublishService


class ValidationPresentService(BaseService):
    """Mark a validation as presented."""

    def run(self, *, validation: Validation, reviewer) -> Validation:
        try:
            validation.present(reviewer=reviewer)
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        validation.save(update_fields=["state", "presented_at", "reviewer", "updated_at"])
        return validation


class ValidationRejectService(BaseService):
    """Return a presented validation back to preparation."""

    def run(self, *, validation: Validation, notes: Optional[str] = None) -> Validation:
        try:
            validation.reset(notes=notes)
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        update_fields = ["state", "validated_at", "updated_at"]
        if notes is not None:
            update_fields.append("notes")
        validation.save(update_fields=update_fields)
        return validation


class ValidationAcceptService(BaseService):
    """Accept a presented validation and advance the opportunity."""

    def run(self, *, validation: Validation) -> Validation:
        try:
            validation.accept()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        validation.save(update_fields=["state", "validated_at", "updated_at"])

        opportunity = validation.opportunity
        if opportunity.state == Opportunity.State.VALIDATING:
            OpportunityPublishService.call(opportunity=opportunity)
        return validation
