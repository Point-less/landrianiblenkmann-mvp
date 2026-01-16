from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django_fsm import can_proceed


class FSMTransitionMixin:
    """Common helpers for FSM-managed models (transition checks)."""

    def can_transition(self, transition_name: str, *, field: str = "state") -> bool:
        method = getattr(self, transition_name, None)
        if not callable(method):
            return False
        return can_proceed(method)

    def available_transitions(self, *, field: str = "state"):
        getter = getattr(self, f"get_available_{field}_transitions", None)
        if callable(getter):
            return getter()
        return []


class FSMAuditMixin(models.Model):
    """Attach transition history entries to a model instance."""
    state_transitions = GenericRelation(
        "utils.FSMStateTransition",
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="%(app_label)s_%(class)s_state_transitions",
    )

    class Meta:
        abstract = True

class FSMTrackingMixin(FSMTransitionMixin, FSMAuditMixin):
    """Convenience mixin combining transition helpers with logging."""

    class Meta:
        abstract = True



class TimeStampedMixin(models.Model):
    """Abstract mixin adding created/updated auditing fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TimeStampedModel(TimeStampedMixin):
    class Meta(TimeStampedMixin.Meta):
        abstract = True


__all__ = [
    'TimeStampedMixin',
    'TimeStampedModel',
    'FSMTrackingMixin',
]
