from types import SimpleNamespace

from django.test import TestCase

from core.models import Agent, Contact, Currency, Property
from integrations.models import TokkobrokerProperty
from intentions.models import ProviderIntention, SeekerIntention
from opportunities.models import OperationType, ProviderOpportunity, SeekerOpportunity
from opportunities.schema import (
    _resolve_operation_agreements,
    _resolve_provider_opportunities,
    _resolve_seeker_opportunities,
)
from opportunities.filters import ProviderOpportunityFilter, SeekerOpportunityFilter
from users.models import User


def _ctx(user):
    return SimpleNamespace(context=SimpleNamespace(request=SimpleNamespace(user=user)))


class OpportunitiesSchemaFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", "admin@example.com", "pass")
        self.currency = Currency.objects.create(code="USD", name="US Dollar")
        self.op_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})

        self.agent = Agent.objects.create(first_name="A", last_name="One")
        self.contact = Contact.objects.create(first_name="C", last_name="One", email="c1@example.com")
        self.property = Property.objects.create(name="House 1")
        self.tokko = TokkobrokerProperty.objects.create(tokko_id=1, ref_code="TK1")

        self.provider_intention = ProviderIntention.objects.create(
            owner=self.contact,
            agent=self.agent,
            property=self.property,
            operation_type=self.op_type,
        )
        self.provider_intention_alt = ProviderIntention.objects.create(
            owner=self.contact,
            agent=self.agent,
            property=self.property,
            operation_type=self.op_type,
        )
        self.seeker_intention = SeekerIntention.objects.create(
            contact=self.contact,
            agent=self.agent,
            operation_type=self.op_type,
            currency=self.currency,
            budget_min=100,
            budget_max=200,
        )
        self.seeker_intention_alt = SeekerIntention.objects.create(
            contact=self.contact,
            agent=self.agent,
            operation_type=self.op_type,
            currency=self.currency,
            budget_min=300,
            budget_max=400,
        )

        self.provider_opportunity = ProviderOpportunity.objects.create(
            source_intention=self.provider_intention,
            tokkobroker_property=self.tokko,
            state=ProviderOpportunity.State.MARKETING,
        )
        self.other_provider_opportunity = ProviderOpportunity.objects.create(
            source_intention=self.provider_intention_alt,
            tokkobroker_property=TokkobrokerProperty.objects.create(tokko_id=2, ref_code="TK2"),
            state=ProviderOpportunity.State.MARKETING,
        )

        self.seeker_opportunity = SeekerOpportunity.objects.create(
            source_intention=self.seeker_intention,
            state=SeekerOpportunity.State.MATCHING,
        )
        self.other_seeker_opportunity = SeekerOpportunity.objects.create(
            source_intention=self.seeker_intention_alt,
            state=SeekerOpportunity.State.NEGOTIATING,
        )

    def test_provider_opportunities_filtered_by_id(self):
        filters = ProviderOpportunityFilter(id=self.provider_opportunity.id, state=None, source_intention_id=None)
        qs = _resolve_provider_opportunities(None, _ctx(self.user), filters)
        self.assertEqual(list(qs), [self.provider_opportunity])

    def test_seeker_opportunities_filtered_by_state(self):
        filters = SeekerOpportunityFilter(id=None, state=self.seeker_opportunity.state, source_intention_id=None)
        qs = _resolve_seeker_opportunities(None, _ctx(self.user), filters)
        self.assertEqual(set(qs), {self.seeker_opportunity})

    def test_operation_agreements_without_filters_returns_queryset(self):
        qs = _resolve_operation_agreements(None, _ctx(self.user), None)
        self.assertEqual(qs.count(), 0)
