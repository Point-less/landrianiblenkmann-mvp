"""Helpers for propagating the current acting user across layers."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator

from django.contrib.auth.models import AbstractBaseUser

ActorType = AbstractBaseUser | None

_current_actor: ContextVar[ActorType] = ContextVar("current_actor", default=None)


def get_current_actor() -> ActorType:
    """Return the user currently bound to the execution context, if any."""

    return _current_actor.get(None)


@contextmanager
def actor_context(actor: ActorType) -> Iterator[ActorType]:
    """Bind an actor for the duration of the block, restoring afterwards.

    If ``actor`` is falsy/None, the current context is left unchanged.
    """

    if actor is None:
        yield None
        return

    token: Token = _current_actor.set(actor)
    try:
        yield actor
    finally:
        _current_actor.reset(token)


__all__ = [
    "actor_context",
    "get_current_actor",
]
