from typing import Optional

from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import Opportunity, Validation
from core.services.base import BaseService
from core.services.opportunities import OpportunityPublishService


class ValidationBaseService(BaseService):
    def ensure_state(self, validation: Validation, expected: Validation.State) -> None:
        if validation.state != expected:
            raise ValidationError(
                f"Validation must be in '{expected}' state; current state is '{validation.state}'."
            )


class ValidationPresentService(ValidationBaseService):
    """Mark a validation as presented."""

    def run(self, *, validation: Validation, reviewer) -> Validation:
        self.ensure_state(validation, Validation.State.PREPARING)
        validation.state = Validation.State.PRESENTED
        validation.presented_at = timezone.now()
        validation.reviewer = reviewer
        validation.save(update_fields=["state", "presented_at", "reviewer", "updated_at"])
        return validation


class ValidationRejectService(ValidationBaseService):
    """Return a presented validation back to preparation."""

    def run(self, *, validation: Validation, notes: Optional[str] = None) -> Validation:
        self.ensure_state(validation, Validation.State.PRESENTED)
        validation.state = Validation.State.PREPARING
        validation.validated_at = None
        if notes is not None:
            validation.notes = notes
            validation.save(update_fields=["state", "validated_at", "notes", "updated_at"])
        else:
            validation.save(update_fields=["state", "validated_at", "updated_at"])
        return validation


class ValidationAcceptService(ValidationBaseService):
    """Accept a presented validation and advance the opportunity."""

    def run(self, *, validation: Validation) -> Validation:
        self.ensure_state(validation, Validation.State.PRESENTED)
        validation.state = Validation.State.ACCEPTED
        validation.validated_at = timezone.now()
        validation.save(update_fields=["state", "validated_at", "updated_at"])

        opportunity = validation.opportunity
        if opportunity.state == Opportunity.State.VALIDATING:
            OpportunityPublishService.call(opportunity=opportunity)
        return validation
