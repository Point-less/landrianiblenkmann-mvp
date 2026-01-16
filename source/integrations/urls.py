"""Integration routes (Tokkobroker, future providers)."""

from django.urls import path

from integrations import views

urlpatterns = [
    path('tokko/sync-now/', views.TokkoSyncRunView.as_view(), name='integration-tokko-sync-now'),
    path('tokko/enqueue/', views.TokkoSyncEnqueueView.as_view(), name='integration-tokko-sync-enqueue'),
    path('tokko/clear/', views.TokkoClearView.as_view(), name='integration-tokko-clear'),
    path('tokko/properties/search/', views.TokkoPropertySearchView.as_view(), name='integration-tokko-properties-search'),
    path('zonaprop/sync-now/', views.ZonapropSyncRunView.as_view(), name='integration-zonaprop-sync-now'),
    path('zonaprop/enqueue/', views.ZonapropSyncEnqueueView.as_view(), name='integration-zonaprop-sync-enqueue'),
    path('zonaprop/clear/', views.ZonapropClearView.as_view(), name='integration-zonaprop-clear'),
    path(
        'zonaprop/publications/<int:publication_id>/',
        views.ZonapropPublicationDetailView.as_view(),
        name='integration-zonaprop-publication-detail',
    ),
]
