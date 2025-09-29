from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import GraphQLView

from .schema import schema as main_schema


@method_decorator(csrf_exempt, name="dispatch")
class AuthenticatedGraphQLView(LoginRequiredMixin, GraphQLView):
    graphiql = True
    login_url = '/admin/login/'

    @classmethod
    def as_view(cls, **initkwargs):
        return super().as_view(schema=main_schema, **initkwargs)


def graphql_view():
    return AuthenticatedGraphQLView.as_view()
