from typing import Any, Mapping, Optional

from django.core.exceptions import ValidationError
from django.utils import timezone

from opportunities.models import AcquisitionAttempt, Appraisal, Opportunity, Validation

from .base import BaseService
from .opportunities import OpportunityValidateService


class AcquisitionAttemptService(BaseService):
    """Base helper with shared validation utilities."""

    def ensure_state(self, attempt: AcquisitionAttempt, expected: AcquisitionAttempt.State) -> None:
        if attempt.state != expected:
            raise ValidationError(
                f"Acquisition attempt must be in '{expected}' state; current state is '{attempt.state}'."
            )


class AcquisitionAttemptAppraiseService(AcquisitionAttemptService):
    """Transition a valuating attempt into negotiating, optionally capturing appraisal data."""

    def run(
        self,
        *,
        attempt: AcquisitionAttempt,
        appraisal_data: Optional[Mapping[str, Any]] = None,
    ) -> AcquisitionAttempt:
        self.ensure_state(attempt, AcquisitionAttempt.State.VALUATING)

        attempt.state = AcquisitionAttempt.State.NEGOTIATING
        attempt.save(update_fields=["state", "updated_at"])

        if appraisal_data:
            Appraisal.objects.update_or_create(
                attempt=attempt,
                defaults={**appraisal_data, "attempt": attempt},
            )

        return attempt


class AcquisitionAttemptCaptureService(AcquisitionAttemptService):
    """Mark the attempt as captured/closed and advance the opportunity."""

    def run(self, *, attempt: AcquisitionAttempt, actor: Optional[Any] = None) -> AcquisitionAttempt:
        self.ensure_state(attempt, AcquisitionAttempt.State.NEGOTIATING)

        attempt.state = AcquisitionAttempt.State.CLOSED
        attempt.closed_at = timezone.now()
        attempt.save(update_fields=["state", "closed_at", "updated_at"])

        opportunity = attempt.opportunity
        if opportunity.state == Opportunity.State.CAPTURING:
            OpportunityValidateService.call(opportunity=opportunity, actor=actor)

        Validation.objects.get_or_create(
            opportunity=opportunity,
            defaults={"state": Validation.State.PREPARING},
        )

        return attempt


class AcquisitionAttemptRejectService(AcquisitionAttemptService):
    """Reject the attempt without moving the opportunity forward."""

    def run(self, *, attempt: AcquisitionAttempt, notes: str | None = None) -> AcquisitionAttempt:
        self.ensure_state(attempt, AcquisitionAttempt.State.NEGOTIATING)

        update_fields = ["state", "closed_at", "updated_at"]
        attempt.state = AcquisitionAttempt.State.CLOSED
        attempt.closed_at = timezone.now()
        if notes:
            attempt.notes = notes
            update_fields.append("notes")
        attempt.save(update_fields=update_fields)

        return attempt
