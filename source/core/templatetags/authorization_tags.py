from django import template

from utils import authorization


register = template.Library()


@register.simple_tag(takes_context=True)
def can(context, action_code, obj=None):
    """Return True/False for template gating without re-encoding rules."""

    user = context["request"].user
    try:
        authorization.check(user, authorization.Action(action_code), obj)
        return True
    except Exception:
        return False
