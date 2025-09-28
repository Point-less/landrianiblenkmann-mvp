from typing import List

import strawberry
import strawberry_django
from django.contrib.auth import get_user_model

UserModel = get_user_model()


@strawberry_django.type(
    UserModel,
    fields=("id", "username", "email", "first_name", "last_name"),
)
class UserType:
    pass


@strawberry.type
class Query:
    users: List[UserType] = strawberry_django.field()


schema = strawberry.Schema(query=Query)
