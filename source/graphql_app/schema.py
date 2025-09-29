from typing import Iterable, Optional

import strawberry
import strawberry_django
from strawberry import relay

from django.contrib.auth import get_user_model

UserModel = get_user_model()


@strawberry.input
class UserFilterInput:
    username: Optional[str] = None
    email: Optional[str] = None
    is_staff: Optional[bool] = None
    is_active: Optional[bool] = None


@strawberry_django.type(UserModel, fields="__all__")
class UserType(relay.Node):
    pass


@strawberry.type
class Query:
    @relay.connection(relay.ListConnection[UserType])
    def users(self, info, filters: Optional[UserFilterInput] = None) -> Iterable[UserModel]:
        queryset = UserModel.objects.all().order_by("id")

        if filters:
            if filters.username:
                queryset = queryset.filter(username__icontains=filters.username)
            if filters.email:
                queryset = queryset.filter(email__icontains=filters.email)
            if filters.is_staff is not None:
                queryset = queryset.filter(is_staff=filters.is_staff)
            if filters.is_active is not None:
                queryset = queryset.filter(is_active=filters.is_active)

        return queryset


schema = strawberry.Schema(query=Query)
