import strawberry
import strawberry_django
from strawberry import relay

from django.contrib.auth import get_user_model


UserModel = get_user_model()


@strawberry_django.type(UserModel, fields="__all__")
class UserType(relay.Node):
    pass


__all__ = ["UserType"]
