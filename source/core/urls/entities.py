"""Core entity routes for agents, contacts, and properties."""

from django.urls import path

from core import views

urlpatterns = [
    path('agents/new/', views.AgentCreateView.as_view(), name='agent-create'),
    path('agents/<int:agent_id>/edit/', views.AgentUpdateView.as_view(), name='agent-edit'),
    path('contacts/new/', views.ContactCreateView.as_view(), name='contact-create'),
    path('contacts/<int:contact_id>/edit/', views.ContactUpdateView.as_view(), name='contact-edit'),
    path('properties/new/', views.PropertyCreateView.as_view(), name='property-create'),
    path('properties/<int:property_id>/edit/', views.PropertyUpdateView.as_view(), name='property-edit'),
]

