from typing import Optional

from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from opportunities.models import Operation

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
