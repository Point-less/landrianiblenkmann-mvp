from __future__ import annotations

from users.models import User
from utils.services import BaseService


class ActiveUserByEmailQuery(BaseService):
    """Fetch an active user by email, raising DoesNotExist when absent."""

    atomic = False

    def run(self, *, email: str):
        return User.objects.get(email=email, is_active=True)


__all__ = ["ActiveUserByEmailQuery"]
