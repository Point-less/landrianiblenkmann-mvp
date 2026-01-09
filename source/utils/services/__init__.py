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
from utils.services.internal.proxy_core import service_proxy, ServiceProxy, for_actor as proxy_for_actor

# Concise alias for the default proxy
S = service_proxy

__all__ = [
    'BaseService',
    'service_atomic',
    'discover_services',
    'get_services',
    'iter_services',
    'resolve_service',
    'for_actor',
    'ServiceInvoker',
    'service_proxy',
    'ServiceProxy',
    'proxy_for_actor',
    'S',
]
