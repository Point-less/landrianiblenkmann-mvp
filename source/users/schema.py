import strawberry
import strawberry_django
from strawberry import relay
from typing import Iterable

from .filters import UserFilter
from .types import UserType
from utils.authorization import USER_VIEW_ALL, check


def _resolve_users(root, info, filters: UserFilter | None = None) -> Iterable[UserType]:
    request = info.context.request
    check(request.user, USER_VIEW_ALL)
    qs = UserType.get_queryset(None, info)
    # strawberry_django will apply filters after resolver returns qs
    return qs


@strawberry.type
class UsersQuery:
    users: relay.ListConnection[UserType] = strawberry_django.connection(  # type: ignore[misc]
        relay.ListConnection[UserType],
        filters=UserFilter,
        resolver=_resolve_users,
    )


__all__ = ["UsersQuery", "UserType"]
