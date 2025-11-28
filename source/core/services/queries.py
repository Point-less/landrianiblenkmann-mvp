"""Read-only query services for core dashboards and forms."""

from __future__ import annotations

from core.models import Agent, Contact, Property, Currency
from intentions.models import SaleProviderIntention, SaleSeekerIntention
from integrations.models import TokkobrokerProperty
from utils.services import BaseService


class AgentsQuery(BaseService):
    def run(self, *, actor=None):
        return Agent.objects.order_by('-created_at')


class ContactsQuery(BaseService):
    def run(self, *, actor=None):
        return Contact.objects.select_related().order_by('-created_at')


class PropertiesQuery(BaseService):
    def run(self, *, actor=None):
        return Property.objects.order_by('-created_at')


class ProviderIntentionsQuery(BaseService):
    def run(self, *, actor=None):
        return (
            SaleProviderIntention.objects.select_related('owner', 'agent', 'property')
            .prefetch_related('state_transitions')
            .order_by('-created_at')
        )


class SeekerIntentionsQuery(BaseService):
    def run(self, *, actor=None):
        return (
            SaleSeekerIntention.objects.select_related('contact', 'agent')
            .prefetch_related('state_transitions')
            .order_by('-created_at')
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
    'SeekerIntentionsQuery',
    'TokkobrokerPropertiesQuery',
    'AvailableTokkobrokerPropertiesQuery',
    'CurrenciesQuery',
]
