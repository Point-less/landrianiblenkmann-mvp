from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import GraphQLView

from .schema import schema


def graphql_view():
    view = GraphQLView.as_view(schema=schema, graphiql=True)
    return csrf_exempt(view)
