"""Core URL routing split into domain modules."""

from django.urls import include, path

from . import dashboard, entities

urlpatterns = []
urlpatterns += dashboard.urlpatterns
urlpatterns += entities.urlpatterns
