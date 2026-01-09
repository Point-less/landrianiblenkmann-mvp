from decimal import Decimal

from django.test import TestCase, override_settings

from integrations.models import TokkobrokerProperty
from integrations.tasks import (
    _parse_tokkobroker_date,
    _publish_marketing_package,
    _unpublish_marketing_package,
    sync_tokkobroker_registry,
)
from opportunities.models import MarketingPackage, MarketingPublication, OperationType, ProviderOpportunity
from core.models import Agent, Contact, Currency, Property
from intentions.models import ProviderIntention


class DummyResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


class DummyClient:
    def __init__(self, responses=None):
        self.calls = []
        self._responses = responses or []

    def call_property_endpoint(self, property_id, payload, action=None):
        self.calls.append((property_id, payload, action))
        if self._responses:
            return self._responses.pop(0)
        return DummyResponse()


class TokkobrokerTaskTests(TestCase):
    def test_parse_tokkobroker_date_handles_formats(self):
        self.assertEqual(_parse_tokkobroker_date("01-12-2024").day, 1)
        self.assertEqual(_parse_tokkobroker_date("2024-12-01").month, 12)
        self.assertIsNone(_parse_tokkobroker_date("bad"))

    def test_sync_registry_creates_property(self):
        count = sync_tokkobroker_registry([
            {"id": 10, "ref_code": "R1", "address": "Addr", "quick_data": {"data": {"created_at": "01-01-2024"}}},
            {"id": "bad"},
        ])
        self.assertEqual(count, 1)
        self.assertTrue(TokkobrokerProperty.objects.filter(tokko_id=10, ref_code="R1").exists())

    @override_settings(TOKKO_SYNC_ENABLED=True)
    def test_publish_marketing_package_happy_path(self):
        client = DummyClient()
        package = self._package(price=Decimal("100000"), currency_code="USD")

        _publish_marketing_package(client, package, property_id=99)

        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[0][1]["OP-1-ENA"], "true")
        self.assertEqual(client.calls[1][1]["OP-1-primary"], "100000")

    def test_publish_marketing_package_skips_without_price(self):
        client = DummyClient()
        package = self._package(price=None, currency_code="USD")
        _publish_marketing_package(client, package, property_id=1)
        self.assertEqual(client.calls, [])

    def test_unpublish_marketing_package(self):
        client = DummyClient()
        package = self._package(price=Decimal("1"), currency_code="USD")
        _unpublish_marketing_package(client, package, property_id=5)
        self.assertEqual(len(client.calls), 1)

    def _package(self, price, currency_code="USD"):
        currency = Currency.objects.create(code=currency_code, name=currency_code)
        op_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})
        agent = Agent.objects.create(first_name="A", last_name="B")
        contact = Contact.objects.create(first_name="C", last_name="D", email="c@example.com")
        prop = Property.objects.create(name="House")
        intention = ProviderIntention.objects.create(owner=contact, agent=agent, property=prop, operation_type=op_type)
        opportunity = ProviderOpportunity.objects.create(
            source_intention=intention,
            tokkobroker_property=TokkobrokerProperty.objects.create(tokko_id=1, ref_code="T1"),
            state=ProviderOpportunity.State.MARKETING,
        )
        package = MarketingPackage.objects.create(
            opportunity=opportunity,
            price=price,
            currency=currency,
        )
        MarketingPublication.objects.create(opportunity=opportunity, package=package, state=MarketingPublication.State.PUBLISHED)
        return package
