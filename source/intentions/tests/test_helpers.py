from decimal import Decimal

from django.test import TestCase

from core.models import Agent, Contact, Currency, Property
from integrations.models import TokkobrokerProperty
from intentions.models import (
    ProviderIntention,
    SeekerIntention,
    _has_provider_opportunity,
    _has_seeker_opportunity,
)
from opportunities.models import OperationType, ProviderOpportunity, SeekerOpportunity


class IntentionHelperTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(first_name="A", last_name="One")
        self.contact = Contact.objects.create(first_name="C", last_name="One", email="c1@example.com")
        self.property = Property.objects.create(name="House 1")
        self.currency = Currency.objects.create(code="USD", name="US Dollar")
        self.op_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})

        self.provider_intention = ProviderIntention.objects.create(
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
            budget_min=Decimal("100"),
            budget_max=Decimal("200"),
        )

    def test_has_provider_opportunity(self):
        self.assertFalse(_has_provider_opportunity(self.provider_intention))

        ProviderOpportunity.objects.create(
            source_intention=self.provider_intention,
            tokkobroker_property=TokkobrokerProperty.objects.create(tokko_id=1, ref_code="TK1"),
            state=ProviderOpportunity.State.MARKETING,
        )

        self.assertTrue(_has_provider_opportunity(self.provider_intention))

    def test_has_seeker_opportunity(self):
        self.assertFalse(_has_seeker_opportunity(self.seeker_intention))

        SeekerOpportunity.objects.create(
            source_intention=self.seeker_intention,
            state=SeekerOpportunity.State.MATCHING,
        )

        self.assertTrue(_has_seeker_opportunity(self.seeker_intention))
