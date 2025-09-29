from django.contrib import admin
from django.urls import path

from core.views import health_check, trigger_log
from users.views import graphql_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health-check'),
    path('trigger-log/', trigger_log, name='trigger-log'),
    path('graphql/', graphql_view(), name='graphql'),
]
