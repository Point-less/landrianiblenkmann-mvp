"""Project-wide service discovery utilities."""

from .registry import discover_services, get_services, iter_services

__all__ = [
    'discover_services',
    'get_services',
    'iter_services',
]
