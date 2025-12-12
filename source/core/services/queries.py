"""Read-only query services for core dashboards and forms."""

from __future__ import annotations

from core.models import Agent, Contact, Property, Currency
from intentions.models import ProviderIntention, SeekerIntention, Valuation
from integrations.models import TokkobrokerProperty
from utils.authorization import (
    AGENT_VIEW,
    CONTACT_VIEW,
    CONTACT_VIEW_ALL,
    PROPERTY_VIEW,
    PROVIDER_INTENTION_VIEW,
    PROVIDER_INTENTION_VIEW_ALL,
    SEEKER_INTENTION_VIEW,
    SEEKER_INTENTION_VIEW_ALL,
    check,
    filter_queryset,
)
from utils.services import BaseService


class AgentsQuery(BaseService):
    def run(self, *, actor=None):
        check(actor, AGENT_VIEW)
        return Agent.objects.order_by('-created_at')


class ContactsQuery(BaseService):
    def run(self, *, actor=None):
        queryset = Contact.objects.select_related().order_by('-created_at')
        return filter_queryset(
            actor,
            CONTACT_VIEW,
            queryset,
            owner_field='agents',
            view_all_action=CONTACT_VIEW_ALL,
        )


class PropertiesQuery(BaseService):
    def run(self, *, actor=None):
        check(actor, PROPERTY_VIEW)
        return Property.objects.order_by('-created_at')


class ProviderIntentionsQuery(BaseService):
    def run(self, *, actor=None):
        queryset = ProviderIntention.objects.select_related('owner', 'agent', 'property').prefetch_related('state_transitions').order_by('-created_at')
        return filter_queryset(
            actor,
            PROVIDER_INTENTION_VIEW,
            queryset,
            owner_field='agent',
            view_all_action=PROVIDER_INTENTION_VIEW_ALL,
        )


class ProviderValuationsQuery(BaseService):
    def run(self, *, actor=None):
        queryset = (
            Valuation.objects.select_related(
                'provider_intention',
                'provider_intention__property',
                'provider_intention__owner',
                'provider_intention__agent',
                'currency',
                'agent',
            )
            .order_by('-delivered_at', '-created_at')
        )
        return filter_queryset(
            actor,
            PROVIDER_INTENTION_VIEW,
            queryset,
            owner_field='agent',
            view_all_action=PROVIDER_INTENTION_VIEW_ALL,
        )


class SeekerIntentionsQuery(BaseService):
    def run(self, *, actor=None):
        queryset = SeekerIntention.objects.select_related('contact', 'agent').prefetch_related('state_transitions').order_by('-created_at')
        return filter_queryset(
            actor,
            SEEKER_INTENTION_VIEW,
            queryset,
            owner_field='agent',
            view_all_action=SEEKER_INTENTION_VIEW_ALL,
        )


class TokkobrokerPropertiesQuery(BaseService):
    def run(self, *, actor=None):
        return TokkobrokerProperty.objects.order_by('-created_at')[:20]


class AvailableTokkobrokerPropertiesQuery(BaseService):
    def run(self, *, actor=None):
        return TokkobrokerProperty.objects.filter(provider_opportunity__isnull=True).order_by('-created_at')


class CurrenciesQuery(BaseService):
    def run(self, *, actor=None):
        return Currency.objects.order_by('code')


__all__ = [
    'AgentsQuery',
    'ContactsQuery',
    'PropertiesQuery',
    'ProviderIntentionsQuery',
    'ProviderValuationsQuery',
    'SeekerIntentionsQuery',
    'TokkobrokerPropertiesQuery',
    'AvailableTokkobrokerPropertiesQuery',
    'CurrenciesQuery',
]
