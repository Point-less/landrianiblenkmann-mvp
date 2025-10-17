from typing import Optional

from django.core.exceptions import ValidationError
from django.utils import timezone

from opportunities.models import Operation, Opportunity

from .base import BaseService


class OperationBaseService(BaseService):
    def ensure_state(self, operation: Operation, expected: Operation.State) -> None:
        if operation.state != expected:
            raise ValidationError(
                f"Operation must be in '{expected}' state; current state is '{operation.state}'."
            )


class OperationReinforceService(OperationBaseService):
    """Transition an offered operation into reinforced."""

    def run(self, *, operation: Operation) -> Operation:
        self.ensure_state(operation, Operation.State.OFFERED)
        operation.state = Operation.State.REINFORCED
        operation.occurred_at = timezone.now()
        operation.save(update_fields=["state", "occurred_at", "updated_at"])
        return operation


class OperationCloseService(OperationBaseService):
    """Close a reinforced operation and mark the opportunity as closed."""

    def run(self, *, operation: Operation, opportunity: Optional[Opportunity] = None) -> Operation:
        self.ensure_state(operation, Operation.State.REINFORCED)
        operation.state = Operation.State.CLOSED
        operation.occurred_at = timezone.now()
        operation.save(update_fields=["state", "occurred_at", "updated_at"])

        opp = opportunity or operation.opportunity
        if opp.state != Opportunity.State.CLOSED:
            opp.state = Opportunity.State.CLOSED
            opp.save(update_fields=["state", "updated_at"])

        return operation


class OperationLoseService(OperationBaseService):
    """Mark a reinforced operation as lost (closed outcome)."""

    def run(self, *, operation: Operation, lost_reason: Optional[str] = None) -> Operation:
        operation = OperationCloseService.call(operation=operation)
        if lost_reason:
            operation.notes = (operation.notes or "") + f"\nLost reason: {lost_reason}"
            operation.save(update_fields=["notes", "updated_at"])
        return operation
