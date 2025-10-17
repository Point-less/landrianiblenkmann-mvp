from contextlib import contextmanager
import inspect

from django.db import DEFAULT_DB_ALIAS, transaction


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

    def __init__(self, *, actor=None):
        self.actor = actor

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

    def _execute(self, *args, **kwargs):
        actor = kwargs.pop("actor", None)
        if actor is None:
            actor = self.actor

        if actor is not None:
            run_signature = inspect.signature(self.run)
            if "actor" in run_signature.parameters and "actor" not in kwargs:
                kwargs["actor"] = actor

        use_atomic = kwargs.pop("use_atomic", None)
        if use_atomic is None:
            use_atomic = self.atomic

        if not use_atomic:
            return self.run(*args, **kwargs)

        with service_atomic(self.using):
            return self.run(*args, **kwargs)


__all__ = ["BaseService", "service_atomic"]
