from __future__ import annotations

from django import template

from utils.services import ServiceProxy, S

register = template.Library()


@register.simple_tag(takes_context=True, name="service")
def service_tag(context, actor=None) -> ServiceProxy:
    """Return a service proxy bound to the current user (or provided actor).

    Usage:
        {% load service_proxy %}
        {% with svc=service %}
            {{ svc.opportunities.DashboardProviderOpportunitiesQuery }}
        {% endwith %}
    """

    if actor is None:
        actor = getattr(context.get("request"), "user", None)
    return ServiceProxy(actor=actor)


@register.simple_tag(name="S")
def service_shortcut(actor=None) -> ServiceProxy:
    """Return the default proxy; optionally bind a specific actor."""

    if actor is None:
        return S
    return ServiceProxy(actor=actor)

