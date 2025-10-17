"""Project-wide service discovery utilities."""

from .base import BaseService, service_atomic
from .registry import (
    ServiceInvoker,
    discover_services,
    for_actor,
    get_services,
    iter_services,
    resolve_service,
)

__all__ = [
    'BaseService',
    'service_atomic',
    'discover_services',
    'get_services',
    'iter_services',
    'resolve_service',
    'for_actor',
    'ServiceInvoker',
]
