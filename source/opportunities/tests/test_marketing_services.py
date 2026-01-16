from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.models import Agent, Contact, Currency, Property
from integrations.models import TokkobrokerProperty
from intentions.models import ProviderIntention
from opportunities.models import MarketingPackage, MarketingPublication, OperationType, ProviderOpportunity, Validation
from opportunities.services.marketing import (
    MarketingPackageActivateService,
    MarketingPackagePauseService,
    MarketingPackageReleaseService,
)


@override_settings(BYPASS_SERVICE_AUTH_FOR_TESTS=True)
class MarketingServiceTests(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(code="USD", name="US Dollar")
        self.op_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})
        self.agent = Agent.objects.create(first_name="Alice", last_name="Agent")
        self.contact = Contact.objects.create(first_name="Owner", last_name="One", email="owner@example.com")
        self.property = Property.objects.create(name="123 Main")
        self.tokko = TokkobrokerProperty.objects.create(tokko_id=2, ref_code="TK2")

        self.intention = ProviderIntention.objects.create(
            owner=self.contact,
            agent=self.agent,
            property=self.property,
            operation_type=self.op_type,
        )
        self.opportunity = ProviderOpportunity.objects.create(
            source_intention=self.intention,
            tokkobroker_property=self.tokko,
            state=ProviderOpportunity.State.MARKETING,
        )
        self.validation = Validation.objects.create(opportunity=self.opportunity, state=Validation.State.APPROVED)
        self.package = MarketingPackage.objects.create(
            opportunity=self.opportunity,
            price=Decimal("100000"),
            currency=self.currency,
        )
        self.publication = MarketingPublication.objects.create(
            opportunity=self.opportunity,
            package=self.package,
            state=MarketingPublication.State.PREPARING,
        )

    def test_activate_package(self):
        svc = MarketingPackageActivateService(actor=None)
        publication = svc(package=self.package)
        self.assertEqual(publication.state, MarketingPublication.State.PUBLISHED)
        self.package.refresh_from_db()
        self.assertEqual(self.package.publication, publication)

    def test_activate_requires_marketing_stage(self):
        self.opportunity.state = ProviderOpportunity.State.VALIDATING
        self.opportunity.save(update_fields=["state", "updated_at"])

        svc = MarketingPackageActivateService(actor=None)
        with self.assertRaises(ValidationError):
            svc(package=self.package, use_atomic=False)

        self.publication.refresh_from_db()
        self.assertEqual(self.publication.state, MarketingPublication.State.PREPARING)

    def test_pause_requires_validation_approved(self):
        self.publication.state = MarketingPublication.State.PUBLISHED
        self.publication.save(update_fields=["state", "updated_at"])

        self.validation.state = Validation.State.PREPARING
        self.validation.save(update_fields=["state", "updated_at"])

        svc = MarketingPackagePauseService(actor=None)
        with self.assertRaises(ValidationError):
            svc(package=self.package)

    def test_release_blocks_active_operation(self):
        self.publication.state = MarketingPublication.State.PAUSED
        self.publication.save(update_fields=["state", "updated_at"])

        # simulate active operation by creating an offered state operation
        from intentions.models import SeekerIntention
        from opportunities.models import Operation, OperationAgreement, SeekerOpportunity

        seeker_intention = SeekerIntention.objects.create(
            contact=self.contact,
            agent=self.agent,
            operation_type=self.op_type,
            currency=self.currency,
            budget_min=Decimal("1"),
            budget_max=Decimal("2"),
        )
        seeker_opp = SeekerOpportunity.objects.create(
            source_intention=seeker_intention,
            state=SeekerOpportunity.State.MATCHING,
        )
        agreement = OperationAgreement.objects.create(
            provider_opportunity=self.opportunity,
            seeker_opportunity=seeker_opp,
            initial_offered_amount=Decimal("120000"),
        )
        Operation.objects.create(
            agreement=agreement,
            initial_offered_amount=Decimal("120000"),
            reserve_amount=Decimal("5000"),
            reserve_deadline=self.validation.created_at.date(),
            currency=self.currency,
        )

        svc = MarketingPackageReleaseService(actor=None)
        with self.assertRaises(ValidationError):
            svc(package=self.package)

    def test_release_blocked_when_opportunity_closed(self):
        self.publication.state = MarketingPublication.State.PAUSED
        self.publication.save(update_fields=["state", "updated_at"])

        self.opportunity.state = ProviderOpportunity.State.CLOSED
        self.opportunity.save(update_fields=["state", "updated_at"])

        self.assertFalse(self.publication.can_transition("publish"))

        svc = MarketingPackageReleaseService(actor=None)
        with self.assertRaises(ValidationError):
            svc(package=self.package, use_atomic=False)
        self.publication.refresh_from_db()
        self.assertEqual(self.publication.state, MarketingPublication.State.PAUSED)

    def _dummy_seeker_intention(self):
        # kept for potential reuse; not used in current tests
        from intentions.models import SeekerIntention
        return SeekerIntention.objects.create(
            contact=self.contact,
            agent=self.agent,
            operation_type=self.op_type,
            currency=self.currency,
            budget_min=Decimal("1"),
            budget_max=Decimal("2"),
        )
