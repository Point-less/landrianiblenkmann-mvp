from django.contrib import admin
from django.urls import path

from core.views import health_check, trigger_log

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health-check'),
    path('trigger-log/', trigger_log, name='trigger-log'),
]
