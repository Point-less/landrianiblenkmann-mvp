from django.urls import path

from .views import health_check, trigger_log

urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('trigger-log/', trigger_log, name='trigger-log'),
]
