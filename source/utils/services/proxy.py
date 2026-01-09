"""Lightweight proxy to access services by app label via the registry.

Usage:
    from utils.services import service_proxy
    service_proxy.opportunities.SeekerOpportunitiesQuery(actor=actor)

By default, it will use the context actor from ``utils.actors.get_current_actor``
unless an explicit ``actor`` kwarg is provided on the call or the proxy/namespace
is instantiated with a default actor.
"""

from __future__ import annotations

from typing import Any, Callable

from utils.actors import get_current_actor
from utils.services.registry import resolve_service


class _ServiceNamespace:
    """Namespace for a specific app label (e.g., ``opportunities``)."""

    def __init__(self, app_label: str, *, actor=None):
        self._app_label = app_label
        self._default_actor = actor

    def __getattr__(self, name: str) -> Callable[..., Any]:
        try:
            service_cls = resolve_service(name, app_label=self._app_label)
        except LookupError as exc:  # pragma: no cover - defensive
            raise AttributeError(str(exc)) from exc

        def _invoke(*args, actor=None, **kwargs):
            svc_actor = actor if actor is not None else (self._default_actor or get_current_actor())
            return service_cls(actor=svc_actor)(*args, **kwargs)

        _invoke.__name__ = name
        _invoke.__qualname__ = f"{self.__class__.__name__}.{name}"
        _invoke.__doc__ = service_cls.__doc__
        return _invoke


class ServiceProxy:
    """Root proxy that exposes app-label namespaces as attributes."""

    def __init__(self, *, actor=None):
        self._default_actor = actor

    def __getattr__(self, app_label: str) -> _ServiceNamespace:
        return _ServiceNamespace(app_label, actor=self._default_actor)


def for_actor(actor) -> ServiceProxy:
    """Return a proxy bound to a default actor."""

    return ServiceProxy(actor=actor)


# Default proxy using context actor when none provided.
service_proxy = ServiceProxy()


__all__ = ["service_proxy", "ServiceProxy", "for_actor"]
