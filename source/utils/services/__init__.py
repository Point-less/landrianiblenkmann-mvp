"""Project-wide service discovery utilities."""

from .registry import (
    ServiceInvoker,
    discover_services,
    for_actor,
    get_services,
    iter_services,
    resolve_service,
)

__all__ = [
    'discover_services',
    'get_services',
    'iter_services',
    'resolve_service',
    'for_actor',
    'ServiceInvoker',
]
