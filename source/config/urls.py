from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from .graphql import graphql_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('graphql/', graphql_view(), name='graphql'),
    path('', include('core.urls')),
    path('', include('intentions.urls')),
    path('', include('opportunities.urls')),
    path('', include('integrations.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
