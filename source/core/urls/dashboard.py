"""Dashboard and system endpoints."""

from django.urls import path
from django.views.generic import RedirectView

from core import views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='workflow-dashboard', permanent=False)),
    path('dashboard/', views.DashboardSectionView.as_view(), name='workflow-dashboard'),
    path('dashboard/<str:section>/', views.DashboardSectionView.as_view(), name='workflow-dashboard-section'),
    path('health/', views.health_check, name='health-check'),
    path('trigger-log/', views.trigger_log, name='trigger-log'),
    path(
        'transitions/<str:app_label>/<str:model>/<int:object_id>/',
        views.ObjectTransitionHistoryView.as_view(),
        name='transition-history',
    ),
]

