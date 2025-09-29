import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from django.conf import settings
from django.core.asgi import get_asgi_application
from servestatic import ServeStaticASGI
from strawberry.asgi import GraphQL

from users.schema import schema

django_asgi_app = get_asgi_application()

graphql_app = GraphQL(schema, graphiql=True)

static_app = ServeStaticASGI(
    django_asgi_app,
    root=settings.STATIC_ROOT,
    prefix=settings.STATIC_URL,
    autorefresh=settings.DEBUG,
)


async def application(scope, receive, send):
    if scope.get("path", "").startswith("/graphql"):
        await graphql_app(scope, receive, send)
    else:
        await static_app(scope, receive, send)
