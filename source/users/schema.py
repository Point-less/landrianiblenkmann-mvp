import strawberry
import strawberry_django
from strawberry import relay

from django.contrib.auth import get_user_model

from .filters import UserFilter

UserModel = get_user_model()


@strawberry_django.type(UserModel, fields="__all__")
class UserType(relay.Node):
    pass


@strawberry.type
class Query:
    users: relay.ListConnection[UserType] = strawberry_django.connection(  # type: ignore[misc]
        filters=UserFilter,
    )


schema = strawberry.Schema(query=Query)
