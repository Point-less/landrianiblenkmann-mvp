from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from core import views as core_views
from .graphql import graphql_view

urlpatterns = [
    # Dashboard at root level
    path('', RedirectView.as_view(pattern_name='workflow-dashboard', permanent=False)),
    path('dashboard/', core_views.DashboardSectionView.as_view(), name='workflow-dashboard'),
    path('dashboard/<str:section>/', core_views.DashboardSectionView.as_view(), name='workflow-dashboard-section'),
    # Other root-level routes
    path('admin/', admin.site.urls),
    path('graphql/', graphql_view(), name='graphql'),
    # App-specific routes
    path('core/', include('core.urls')),
    path('intentions/', include('intentions.urls')),
    path('opportunities/', include('opportunities.urls')),
    path('integrations/', include('integrations.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
