from __future__ import annotations

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from utils.mixins import TimeStampedMixin


class FSMStateTransition(TimeStampedMixin):
    """Historical record of FSM transitions for any model using FSMLoggableMixin."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    state_field = models.CharField(max_length=64)
    from_state = models.CharField(max_length=64, blank=True)
    to_state = models.CharField(max_length=64)
    transition = models.CharField(max_length=128, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ('-occurred_at', '-id')
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['state_field']),
            models.Index(fields=['occurred_at']),
        ]
        verbose_name = 'FSM state transition'
        verbose_name_plural = 'FSM state transitions'

    def __str__(self) -> str:  # pragma: no cover - simple helper
        return f"{self.content_object} {self.from_state}->{self.to_state}"


__all__ = ["FSMStateTransition"]
