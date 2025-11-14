"""Integration routes (Tokkobroker, future providers)."""

from django.urls import path

from core import views as workflow_views

urlpatterns = [
    path('integrations/tokko/sync-now/', workflow_views.TokkoSyncRunView.as_view(), name='integration-tokko-sync-now'),
    path('integrations/tokko/enqueue/', workflow_views.TokkoSyncEnqueueView.as_view(), name='integration-tokko-sync-enqueue'),
    path('integrations/tokko/clear/', workflow_views.TokkoClearView.as_view(), name='integration-tokko-clear'),
]

