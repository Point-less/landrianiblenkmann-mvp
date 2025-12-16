from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.models import Agent, Contact, Currency, Property
from integrations.models import TokkobrokerProperty
from intentions.models import ProviderIntention, SeekerIntention
from opportunities.models import (
    MarketingPackage,
    OperationAgreement,
    OperationType,
    ProviderOpportunity,
    SeekerOpportunity,
    Validation,
)
from opportunities.services.operations import CreateOperationService


@override_settings(BYPASS_SERVICE_AUTH_FOR_TESTS=True)
class CreateOperationServiceTests(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(code="USD", name="US Dollar")
        self.op_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})

        self.agent = Agent.objects.create(first_name="Alice", last_name="Agent")
        self.contact = Contact.objects.create(first_name="Owner", last_name="One", email="owner@example.com")
        self.seeker_contact = Contact.objects.create(first_name="Buyer", last_name="One", email="buyer@example.com")
        self.property = Property.objects.create(name="123 Main")

        self.tokko = TokkobrokerProperty.objects.create(tokko_id=10, ref_code="TK10")
        self.tokko_other = TokkobrokerProperty.objects.create(tokko_id=11, ref_code="TK11")

        self.provider_intention = ProviderIntention.objects.create(
            owner=self.contact,
            agent=self.agent,
            property=self.property,
            operation_type=self.op_type,
        )
        self.seeker_intention = SeekerIntention.objects.create(
            contact=self.seeker_contact,
            agent=self.agent,
            operation_type=self.op_type,
            currency=self.currency,
            budget_min=Decimal("100000"),
            budget_max=Decimal("150000"),
        )

        self.provider_opportunity = ProviderOpportunity.objects.create(
            source_intention=self.provider_intention,
            tokkobroker_property=self.tokko,
            state=ProviderOpportunity.State.MARKETING,
        )
        self.seeker_opportunity = SeekerOpportunity.objects.create(
            source_intention=self.seeker_intention,
            state=SeekerOpportunity.State.MATCHING,
        )

        self.validation = Validation.objects.create(
            opportunity=self.provider_opportunity,
            state=Validation.State.APPROVED,
        )

        self.agreement = OperationAgreement.objects.create(
            provider_opportunity=self.provider_opportunity,
            seeker_opportunity=self.seeker_opportunity,
            initial_offered_amount=Decimal("120000"),
        )

        self.package = MarketingPackage.objects.create(
            opportunity=self.provider_opportunity,
            state=MarketingPackage.State.PUBLISHED,
        )

        self.service = CreateOperationService(actor=None)

    def test_requires_currency(self):
        with self.assertRaisesMessage(ValidationError, "Currency is required"):
            self.service(
                agreement=self.agreement,
                signed_document=None,
                reserve_amount=Decimal("5000"),
                reserve_deadline=date.today(),
                initial_offered_amount=Decimal("120000"),
                currency=None,
            )

    def test_requires_initial_offer(self):
        with self.assertRaisesMessage(ValidationError, "Initial offered amount is required"):
            self.service(
                agreement=self.agreement,
                signed_document=None,
                reserve_amount=Decimal("5000"),
                reserve_deadline=date.today(),
                initial_offered_amount=None,
                currency=self.currency,
            )

    def test_requires_approved_validation(self):
        self.validation.state = Validation.State.PREPARING
        self.validation.save(update_fields=["state", "updated_at"])

        with self.assertRaisesMessage(ValidationError, "Provider validation must be approved"):
            self.service(
                agreement=self.agreement,
                signed_document=None,
                reserve_amount=Decimal("5000"),
                reserve_deadline=date.today(),
                initial_offered_amount=Decimal("120000"),
                currency=self.currency,
            )

    def test_pauses_marketing_packages_when_creating_operation(self):
        operation = self.service(
            agreement=self.agreement,
            signed_document=None,
            reserve_amount=Decimal("5000"),
            reserve_deadline=date.today(),
            initial_offered_amount=Decimal("120000"),
            currency=self.currency,
        )

        self.package.refresh_from_db()
        self.assertEqual(self.package.state, MarketingPackage.State.PAUSED)
        self.assertEqual(operation.currency, self.currency)
