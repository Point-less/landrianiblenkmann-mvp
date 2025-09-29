from django.contrib import admin
from django.urls import include, path

from .graphql import graphql_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('graphql/', graphql_view(), name='graphql'),
    path('', include('core.urls')),
]
