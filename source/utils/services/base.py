from contextlib import contextmanager
import inspect
from typing import Any

from django.db import DEFAULT_DB_ALIAS, transaction

from utils.actors import actor_context

@contextmanager
def service_atomic(using: str | None = None):
    """Atomic block that avoids nesting a new savepoint when already inside one."""

    alias = using or DEFAULT_DB_ALIAS
    connection = transaction.get_connection(alias)
    if connection.in_atomic_block:
        with transaction.atomic(using=alias, savepoint=False):
            yield
    else:
        with transaction.atomic(using=alias):
            yield


class BaseService:
    """Minimal service abstraction that wraps executions in a transaction."""

    atomic = True
    using = DEFAULT_DB_ALIAS
    required_action = None  # Optional utils.authorization.Action for coarse-grain authorization

    def __init__(self, *, actor=None):
        self.actor = actor
        # Avoid importing ServiceProxy here to prevent cycles; type kept broad.
        self._services_proxy: Any = None

    def __call__(self, *args, **kwargs):
        call_actor = kwargs.pop("actor", None)
        if call_actor is not None:
            self.actor = call_actor
        return self._execute(*args, **kwargs)

    @classmethod
    def call(cls, *args, **kwargs):
        call_actor = kwargs.pop("actor", None)
        instance = cls(actor=call_actor)
        return instance(*args, **kwargs)

    def run(self, *args, **kwargs):  # pragma: no cover - abstract
        raise NotImplementedError

    @property
    def services(self):
        """Lazy service proxy bound to this service's actor."""

        from utils.services.internal.proxy_core import ServiceProxy  # inline import to avoid circular dependency

        return ServiceProxy(actor=self.actor)

    @property
    def s(self):
        """Alias for services (concise)."""

        return self.services

    def _execute(self, *args, **kwargs):
        actor = kwargs.pop("actor", None)
        if actor is None:
            actor = self.actor

        # Authorization check (single source of truth)
        if self.required_action is not None:
            from django.conf import settings
            bypass = getattr(settings, "BYPASS_SERVICE_AUTH_FOR_TESTS", False)
            try:
                from utils.authorization import check  # local import avoids cycles
            except Exception:  # pragma: no cover - defensive: authorization not ready
                check = None
            if check is not None and not bypass:
                check(actor, self.required_action)

        if actor is not None:
            run_signature = inspect.signature(self.run)
            if "actor" in run_signature.parameters and "actor" not in kwargs:
                kwargs["actor"] = actor

        use_atomic = kwargs.pop("use_atomic", None)
        if use_atomic is None:
            use_atomic = self.atomic

        if not use_atomic:
            with actor_context(actor):
                return self.run(*args, **kwargs)

        with actor_context(actor):
            with service_atomic(self.using):
                return self.run(*args, **kwargs)


__all__ = ["BaseService", "service_atomic"]
