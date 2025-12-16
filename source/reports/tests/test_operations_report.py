from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings

from core.models import Agent, Contact, Currency, Property
from integrations.models import TokkobrokerProperty
from intentions.models import ProviderIntention, SeekerIntention
from opportunities.models import Operation, OperationAgreement, OperationType, ProviderOpportunity, SeekerOpportunity, Validation
from reports.services.operations import ClosedOperationsFinancialReportQuery


@override_settings(BYPASS_SERVICE_AUTH_FOR_TESTS=True)
class ClosedOperationsFinancialReportQueryTests(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(code="USD", name="US Dollar")
        self.op_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})

        self.agent = Agent.objects.create(first_name="Alice", last_name="Agent", commission_split=Decimal("0.5"))
        self.agent_buyer = Agent.objects.create(first_name="Bob", last_name="Buyer", commission_split=Decimal("0.25"))

        self.seller = Contact.objects.create(first_name="Seller", last_name="One", email="s@example.com", tax_id="20-1")
        self.buyer = Contact.objects.create(first_name="Buyer", last_name="Two", email="b@example.com", tax_id="20-2")
        self.property = Property.objects.create(name="123 Main", full_address="123 Main St")
        self.tokko = TokkobrokerProperty.objects.create(tokko_id=3, ref_code="TK3")

        self.provider_intention = ProviderIntention.objects.create(
            owner=self.seller,
            agent=self.agent,
            property=self.property,
            operation_type=self.op_type,
        )
        self.seeker_intention = SeekerIntention.objects.create(
            contact=self.buyer,
            agent=self.agent_buyer,
            operation_type=self.op_type,
            currency=self.currency,
            budget_min=Decimal("100000"),
            budget_max=Decimal("150000"),
        )

        self.provider_opp = ProviderOpportunity.objects.create(
            source_intention=self.provider_intention,
            tokkobroker_property=self.tokko,
            state=ProviderOpportunity.State.MARKETING,
            gross_commission_pct=Decimal("0.04"),
        )
        self.seeker_opp = SeekerOpportunity.objects.create(
            source_intention=self.seeker_intention,
            state=SeekerOpportunity.State.NEGOTIATING,
            gross_commission_pct=Decimal("0.03"),
        )
        Validation.objects.create(opportunity=self.provider_opp, state=Validation.State.APPROVED)

        self.agreement = OperationAgreement.objects.create(
            provider_opportunity=self.provider_opp,
            seeker_opportunity=self.seeker_opp,
            initial_offered_amount=Decimal("120000"),
            state=OperationAgreement.State.AGREED,
        )
        self.operation = Operation.objects.create(
            agreement=self.agreement,
            initial_offered_amount=Decimal("120000"),
            reserve_amount=Decimal("5000"),
            reserve_deadline=date.today(),
            currency=self.currency,
            offered_amount=Decimal("125000"),
            declared_deed_value=Decimal("110000"),
        )
        self.operation.reinforce()
        self.operation.close()
        self.operation.save(update_fields=["state", "occurred_at", "updated_at"])

    def test_report_rows_include_buyer_and_seller(self):
        rows = ClosedOperationsFinancialReportQuery(actor=self._superuser())()
        self.assertEqual(len(rows), 2)

        seller_row = next(r for r in rows if r["role"] == "Seller")
        buyer_row = next(r for r in rows if r["role"] == "Buyer")

        self.assertEqual(seller_row["client_name"], "Seller One")
        self.assertEqual(buyer_row["client_name"], "Buyer Two")
        self.assertEqual(seller_row["deal_value"], Decimal("125000"))
        self.assertEqual(buyer_row["agent_split"], self.agent_buyer.commission_split)

    def _superuser(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return User.objects.create_superuser("admin", "admin@example.com", "pass")
