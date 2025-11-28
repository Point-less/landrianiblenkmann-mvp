from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.dispatch import receiver
from django_fsm.signals import post_transition

from utils.actors import get_current_actor
from utils.mixins import FSMLoggableMixin
from utils.models import FSMStateTransition


@receiver(post_transition)
def record_fsm_transition(sender, instance, name, source, target, **kwargs):
    if not isinstance(instance, FSMLoggableMixin):
        return
    if instance.pk is None:
        return

    field = kwargs.get('field')
    state_field = field.name if field is not None else 'state'

    FSMStateTransition.objects.create(
        content_type=ContentType.objects.get_for_model(instance, for_concrete_model=False),
        object_id=instance.pk,
        actor=get_current_actor(),
        state_field=state_field,
        from_state=source or '',
        to_state=target or '',
        transition=name or '',
        occurred_at=timezone.now(),
    )
