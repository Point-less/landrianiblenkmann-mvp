from typing import List

import strawberry
import strawberry_django
from django.contrib.auth import get_user_model

UserModel = get_user_model()


@strawberry_django.type(UserModel)
class UserType:
    id: strawberry.auto
    username: strawberry.auto
    email: strawberry.auto
    first_name: strawberry.auto
    last_name: strawberry.auto


@strawberry.type
class Query:
    users: List[UserType] = strawberry_django.field()


schema = strawberry.Schema(query=Query)
