import os
from django.conf import settings
from django.core.asgi import get_asgi_application
from servestatic import ServeStaticASGI
from strawberry.asgi import GraphQL

from graphql_app.schema import schema

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

graphql_app = GraphQL(schema, graphiql=True)

application = ServeStaticASGI(
    django_asgi_app,
    root=settings.STATIC_ROOT,
    prefix=settings.STATIC_URL,
    autorefresh=settings.DEBUG,
)

async def app(scope, receive, send):
    if scope.get("path", "").startswith("/graphql"):
        await graphql_app(scope, receive, send)
    else:
        await application(scope, receive, send)


application = app
