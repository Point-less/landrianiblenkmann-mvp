"""Integration routes (Tokkobroker, future providers)."""

from django.urls import path

from integrations import views

urlpatterns = [
    path('tokko/sync-now/', views.TokkoSyncRunView.as_view(), name='integration-tokko-sync-now'),
    path('tokko/enqueue/', views.TokkoSyncEnqueueView.as_view(), name='integration-tokko-sync-enqueue'),
    path('tokko/clear/', views.TokkoClearView.as_view(), name='integration-tokko-clear'),
]
