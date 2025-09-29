import strawberry
import strawberry_django

from django.contrib.auth import get_user_model

UserModel = get_user_model()


@strawberry_django.filters.filter(UserModel, lookups=True)
class UserFilter:
    id: strawberry.auto
    username: strawberry.auto
    email: strawberry.auto
    is_staff: strawberry.auto
    is_active: strawberry.auto
