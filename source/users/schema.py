import strawberry
import strawberry_django
from strawberry import relay

from .filters import UserFilter
from .graphql.types import UserType


@strawberry.type
class UsersQuery:
    users: relay.ListConnection[UserType] = strawberry_django.connection(  # type: ignore[misc]
        relay.ListConnection[UserType],
        filters=UserFilter,
    )


__all__ = ["UsersQuery", "UserType"]
