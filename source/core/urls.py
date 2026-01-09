"""Core URL routing - consolidated dashboard, entity, and health check endpoints."""

from django.urls import path

from core import views

urlpatterns = [
    # System endpoints
    path('health/', views.health_check, name='health-check'),
    path('trigger-log/', views.trigger_log, name='trigger-log'),
    path(
        'transitions/<str:app_label>/<str:model>/<int:object_id>/',
        views.ObjectTransitionHistoryView.as_view(),
        name='transition-history',
    ),
    # Core entity routes for agents, contacts, and properties
    path('agents/new/', views.AgentCreateView.as_view(), name='agent-create'),
    path('agents/<int:agent_id>/edit/', views.AgentUpdateView.as_view(), name='agent-edit'),
    path('contacts/new/', views.ContactCreateView.as_view(), name='contact-create'),
    path('contacts/<int:contact_id>/edit/', views.ContactUpdateView.as_view(), name='contact-edit'),
    path('properties/new/', views.PropertyCreateView.as_view(), name='property-create'),
    path('properties/<int:property_id>/edit/', views.PropertyUpdateView.as_view(), name='property-edit'),
]
