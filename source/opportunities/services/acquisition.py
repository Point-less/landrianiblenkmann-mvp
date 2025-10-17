from typing import Any, Mapping, Optional

from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from opportunities.models import AcquisitionAttempt, Appraisal, Opportunity, Validation

from utils.services import BaseService
from .opportunities import OpportunityValidateService


class AcquisitionAttemptAppraiseService(BaseService):
    """Transition a valuating attempt into negotiating, optionally capturing appraisal data."""

    def run(
        self,
        *,
        attempt: AcquisitionAttempt,
        appraisal_data: Optional[Mapping[str, Any]] = None,
    ) -> AcquisitionAttempt:
        try:
            attempt.start_negotiation()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        attempt.save(update_fields=["state", "updated_at"])

        if appraisal_data:
            Appraisal.objects.update_or_create(
                attempt=attempt,
                defaults={**appraisal_data, "attempt": attempt},
            )

        return attempt


class AcquisitionAttemptCaptureService(BaseService):
    """Mark the attempt as captured/closed and advance the opportunity."""

    def run(self, *, attempt: AcquisitionAttempt, actor: Optional[Any] = None) -> AcquisitionAttempt:
        try:
            attempt.close_attempt()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        attempt.save(update_fields=["state", "closed_at", "updated_at"])

        opportunity = attempt.opportunity
        if opportunity.state == Opportunity.State.CAPTURING:
            OpportunityValidateService.call(opportunity=opportunity, actor=actor)

        Validation.objects.get_or_create(
            opportunity=opportunity,
            defaults={"state": Validation.State.PREPARING},
        )

        return attempt


class AcquisitionAttemptRejectService(BaseService):
    """Reject the attempt without moving the opportunity forward."""

    def run(self, *, attempt: AcquisitionAttempt, notes: str | None = None) -> AcquisitionAttempt:
        try:
            attempt.close_attempt(notes=notes)
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        update_fields = ["state", "closed_at", "updated_at"]
        if notes:
            update_fields.append("notes")
        attempt.save(update_fields=update_fields)

        return attempt
