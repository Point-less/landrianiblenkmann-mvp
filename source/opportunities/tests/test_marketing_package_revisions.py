from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Agent, Contact, Currency, Property
from integrations.models import TokkobrokerProperty
from intentions.models import ProviderIntention
from opportunities.models import (
    MarketingPackage,
    MarketingPublication,
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
        self.assertEqual(pkg.version, 1)
        self.assertTrue(pkg.is_active)

        new_pkg = MarketingPackageUpdateService.call(
            actor=None,
            package=pkg,
            headline="Updated headline",
            price=Decimal("105000"),
        )
        self.assertEqual(new_pkg.version, 2)
        self.assertTrue(new_pkg.is_active)

        pkg.refresh_from_db()
        self.assertFalse(pkg.is_active)

        versions = MarketingPackage.objects.filter(opportunity=self.opportunity).order_by("version")
        self.assertEqual(versions.count(), 2)
        self.assertEqual(versions[0].headline, "Initial")
        self.assertEqual(versions[1].headline, "Updated headline")

    def test_transitions_do_not_create_revisions(self):
        pkg = MarketingPackage.objects.create(
            opportunity=self.opportunity,
            price=Decimal("90000"),
            currency=self.currency,
            headline="Prep",
        )
        publication = MarketingPublication.objects.create(
            opportunity=self.opportunity,
            package=pkg,
            state=MarketingPublication.State.PREPARING,
        )
        publication = MarketingPackageActivateService.call(actor=None, package=pkg)
        publication = MarketingPackagePauseService.call(actor=None, package=pkg)

        versions = MarketingPackage.objects.filter(opportunity=self.opportunity)
        self.assertEqual(versions.count(), 1)
        self.assertEqual(publication.state, MarketingPublication.State.PAUSED)

        transitions = list(publication.state_transitions.order_by("-occurred_at"))
        self.assertGreaterEqual(len(transitions), 2)

    def test_query_includes_revisions(self):
        pkg = MarketingPackageCreateService.call(
            actor=None,
            opportunity=self.opportunity,
            headline="Initial",
            price=Decimal("100000"),
            currency=self.currency,
        )
        pkg = MarketingPackageUpdateService.call(actor=None, package=pkg, headline="Second")
        user = get_user_model().objects.create_superuser("admin2", "admin2@example.com", "pass")

        qs = MarketingPackagesWithRevisionsForOpportunityQuery.call(
            actor=user,
            opportunity=self.opportunity,
        )
        packages = list(qs)
        self.assertEqual(len(packages), 2)
        self.assertTrue(any(p.is_active and p.version == 2 for p in packages))
        self.assertTrue(any((not p.is_active) and p.version == 1 for p in packages))


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
        url = reverse("marketing-publication-detail", kwargs={"opportunity_id": self.opportunity.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn("Package version #2", content)
        self.assertIn("#1", content)
        self.assertIn("Second", content)
