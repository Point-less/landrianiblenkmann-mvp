from typing import Optional

from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from opportunities.models import Operation, Opportunity

from utils.services import BaseService


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
    """Close a reinforced operation and mark the opportunity as closed."""

    def run(self, *, operation: Operation, opportunity: Optional[Opportunity] = None) -> Operation:
        try:
            operation.close()
        except TransitionNotAllowed as exc:  # pragma: no cover - defensive guard
            raise ValidationError(str(exc)) from exc

        operation.save(update_fields=["state", "occurred_at", "updated_at"])

        opp = opportunity or operation.opportunity
        if opp.state != Opportunity.State.CLOSED:
            try:
                opp.close_opportunity()
            except TransitionNotAllowed:
                # Opportunity is not ready to close; leave in current state.
                pass
            except ValidationError:
                raise
            else:
                opp.save(update_fields=["state", "updated_at"])

        return operation


class OperationLoseService(BaseService):
    """Mark a reinforced operation as lost (closed outcome)."""

    def run(self, *, operation: Operation, lost_reason: Optional[str] = None) -> Operation:
        operation = OperationCloseService.call(operation=operation)
        if lost_reason:
            operation.notes = (operation.notes or "") + f"\nLost reason: {lost_reason}"
            operation.save(update_fields=["notes", "updated_at"])
        return operation
