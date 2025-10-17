"""Core service utilities and concrete services."""

from .base import BaseService, service_atomic  # noqa: F401
from .opportunities import CreateOpportunityService  # noqa: F401

__all__ = [
    "BaseService",
    "service_atomic",
    "CreateOpportunityService",
    "discover_services",
    "get_services",
    "iter_services",
]

_SERVICE_ATTRS = {
    "discover_services",
    "get_services",
    "iter_services",
}


def __getattr__(name):
    if name in _SERVICE_ATTRS:
        from utils import services as service_registry

        return getattr(service_registry, name)
    raise AttributeError(f"module 'core.services' has no attribute {name!r}")
