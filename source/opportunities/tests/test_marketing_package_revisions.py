from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Agent, Contact, Currency, Property
from integrations.models import TokkobrokerProperty
from intentions.models import ProviderIntention
from opportunities.models import (
    MarketingPackage,
    MarketingPackageRevision,
    OperationType,
    ProviderOpportunity,
    Validation,
)
from opportunities.services.marketing import (
    MarketingPackageActivateService,
    MarketingPackagePauseService,
    MarketingPackageUpdateService,
    MarketingPackageCreateService,
)
from opportunities.services import MarketingPackagesWithRevisionsForOpportunityQuery


@override_settings(BYPASS_SERVICE_AUTH_FOR_TESTS=True)
class MarketingPackageRevisionTests(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(code="USD", name="US Dollar")
        self.op_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})
        self.agent = Agent.objects.create(first_name="Alice", last_name="Agent")
        self.contact = Contact.objects.create(first_name="Owner", last_name="One", email="owner@example.com")
        self.property = Property.objects.create(name="123 Main")
        self.tokko = TokkobrokerProperty.objects.create(tokko_id=42, ref_code="TK42")

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

    def test_revision_created_on_create_and_update(self):
        pkg = MarketingPackageCreateService.call(
            actor=None,
            opportunity=self.opportunity,
            headline="Initial",
            price=Decimal("100000"),
            currency=self.currency,
        )
        revisions = list(pkg.revisions.order_by("version"))
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0].version, 1)
        self.assertTrue(revisions[0].is_active)
        self.assertEqual(revisions[0].headline, "Initial")

        pkg = MarketingPackageUpdateService.call(
            actor=None,
            package=pkg,
            headline="Updated headline",
            price=Decimal("105000"),
        )
        revisions = list(pkg.revisions.order_by("version"))
        self.assertEqual(len(revisions), 2)
        self.assertEqual(revisions[-1].version, 2)
        self.assertTrue(revisions[-1].is_active)
        self.assertEqual(revisions[-1].headline, "Updated headline")
        self.assertFalse(revisions[0].is_active)

    def test_transition_snapshots(self):
        pkg = MarketingPackage.objects.create(
            opportunity=self.opportunity,
            state=MarketingPackage.State.PREPARING,
            price=Decimal("90000"),
            currency=self.currency,
            headline="Prep",
        )
        pkg.snapshot_revision()  # initial snapshot

        pkg = MarketingPackageActivateService.call(actor=None, package=pkg)
        pkg = MarketingPackagePauseService.call(actor=None, package=pkg)
        revisions = list(pkg.revisions.order_by("version"))
        self.assertEqual(len(revisions), 3)  # initial + activate + pause
        states = [rev.state for rev in revisions]
        self.assertEqual(states[-1], MarketingPackage.State.PAUSED)

    def test_query_includes_revisions(self):
        pkg = MarketingPackageCreateService.call(
            actor=None,
            opportunity=self.opportunity,
            headline="Initial",
            price=Decimal("100000"),
            currency=self.currency,
        )
        MarketingPackageUpdateService.call(actor=None, package=pkg, headline="Second")
        user = get_user_model().objects.create_superuser("admin2", "admin2@example.com", "pass")

        qs = MarketingPackagesWithRevisionsForOpportunityQuery.call(
            actor=user,
            opportunity=self.opportunity,
        )
        packages = list(qs)
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0].revisions.count(), 2)


@override_settings(BYPASS_SERVICE_AUTH_FOR_TESTS=True)
class MarketingPackageHistoryViewTests(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(code="USD", name="US Dollar")
        self.op_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})
        self.agent = Agent.objects.create(first_name="Alice", last_name="Agent")
        self.contact = Contact.objects.create(first_name="Owner", last_name="One", email="owner@example.com")
        self.property = Property.objects.create(name="123 Main")
        self.tokko = TokkobrokerProperty.objects.create(tokko_id=7, ref_code="TK7")
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
        Validation.objects.create(opportunity=self.opportunity, state=Validation.State.APPROVED)

        self.package = MarketingPackageCreateService.call(
            actor=None,
            opportunity=self.opportunity,
            headline="Initial",
            price=Decimal("120000"),
            currency=self.currency,
        )
        MarketingPackageUpdateService.call(actor=None, package=self.package, headline="Second")

        user_model = get_user_model()
        self.user = user_model.objects.create_superuser("admin", "admin@example.com", "pass")

    def test_history_view_lists_revisions(self):
        self.client.force_login(self.user)
        url = reverse("marketing-package-history", kwargs={"opportunity_id": self.opportunity.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Should list both versions
        content = resp.content.decode()
        self.assertIn("#1", content)
        self.assertIn("#2", content)
        self.assertIn("Second", content)
