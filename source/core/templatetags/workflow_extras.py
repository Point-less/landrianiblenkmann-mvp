"""Template helpers for workflow dashboards."""

from __future__ import annotations

from django import template
from django_fsm import can_proceed

register = template.Library()


@register.filter(name="can_transition")
def can_transition(obj, transition_name: str) -> bool:
    """Return True if the given FSM transition can proceed on the object."""

    if not obj or not transition_name:
        return False
    transition = getattr(obj, transition_name, None)
    if transition is None:
        return False
    try:
        return bool(can_proceed(transition))
    except Exception:  # pragma: no cover - defensive guard for unexpected attrs
        return False


@register.filter(name="attr")
def attr(obj, attr_name: str):  # pragma: no cover - simple passthrough helper
    return getattr(obj, attr_name)

