from __future__ import annotations

from datetime import date
from decimal import Decimal

import sesame.utils
from sesame import settings as sesame_settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse, get_resolver, URLPattern, URLResolver

from core.models import (
    Agent,
    Contact,
    ContactAgentRelationship,
    Currency,
    Property,
)
from intentions.models import ProviderIntention, SeekerIntention
from integrations.models import TokkobrokerProperty
from opportunities.models import (
    MarketingPackage,
    MarketingPublication,
    Operation,
    OperationAgreement,
    OperationType,
    ProviderOpportunity,
    SeekerOpportunity,
    Validation,
    ValidationDocument,
    ValidationDocumentType,
)
from users.models import Role, RoleMembership, User


class UrlSmokeTests(TestCase):
    """Smoke-test every project URL to ensure views render without server errors."""

    @classmethod
    def setUpTestData(cls):
        cls.password = "pass1234"
        cls.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=cls.password
        )

        cls.currency, _ = Currency.objects.get_or_create(code="USD", defaults={"name": "US Dollar", "symbol": "$"})
        cls.operation_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})

        cls.agent = Agent.objects.create(first_name="Ag", last_name="Ent")
        role_ct = ContentType.objects.get_for_model(Agent)
        agent_role = Role.objects.create(slug="agent", name="Agent", profile_content_type=role_ct)
        RoleMembership.objects.create(user=cls.user, role=agent_role, profile=cls.agent)

        cls.contact = Contact.objects.create(first_name="John", last_name="Doe", email="jd@example.com")
        ContactAgentRelationship.objects.create(agent=cls.agent, contact=cls.contact)
        cls.property = Property.objects.create(name="Sample Property")

        cls.provider_intention = ProviderIntention.objects.create(
            owner=cls.contact,
            agent=cls.agent,
            property=cls.property,
            operation_type=cls.operation_type,
            notes="",
        )

        cls.tokko_property = TokkobrokerProperty.objects.create(
            tokko_id=1, ref_code="REF1", address="123 Main St"
        )

        cls.provider_opportunity = ProviderOpportunity.objects.create(
            source_intention=cls.provider_intention,
            tokkobroker_property=cls.tokko_property,
            contract_expires_on=date.today(),
            contract_effective_on=date.today(),
            valuation_test_value=0,
            valuation_close_value=0,
            gross_commission_pct=Decimal("0.04"),
            state=ProviderOpportunity.State.MARKETING,
        )

        cls.validation = Validation.objects.create(opportunity=cls.provider_opportunity)
        cls.validation.state = Validation.State.APPROVED
        cls.validation.save(update_fields=["state", "updated_at"])
        cls.validation_doc_type = ValidationDocumentType.objects.create(code="doc1", label="Doc 1")
        cls.validation_document = ValidationDocument.objects.create(
            validation=cls.validation,
            document_type=cls.validation_doc_type,
            document=SimpleUploadedFile("doc.txt", b"hello"),
        )

        cls.marketing_package = MarketingPackage.objects.create(
            opportunity=cls.provider_opportunity,
            currency=cls.currency,
        )
        MarketingPublication.objects.create(
            opportunity=cls.provider_opportunity,
            package=cls.marketing_package,
        )

        cls.seeker_intention = SeekerIntention.objects.create(
            contact=cls.contact,
            agent=cls.agent,
            operation_type=cls.operation_type,
            budget_min=0,
            budget_max=100,
            currency=cls.currency,
        )
        cls.seeker_opportunity = SeekerOpportunity.objects.create(
            source_intention=cls.seeker_intention
        )

        cls.operation_agreement = OperationAgreement.objects.create(
            provider_opportunity=cls.provider_opportunity,
            seeker_opportunity=cls.seeker_opportunity,
        )
        cls.operation = Operation.objects.create(
            agreement=cls.operation_agreement,
            initial_offered_amount=Decimal("100"),
            reserve_amount=Decimal("50"),
            reserve_deadline=date.today(),
            currency=cls.currency,
        )

    def setUp(self):
        self.client.login(username=self.user.username, password=self.password)

    def _kwargs_for_names(self):
        return {
            "agent_id": self.agent.pk,
            "contact_id": self.contact.pk,
            "property_id": self.property.pk,
            "intention_id": self.provider_intention.pk,
            "validation_id": self.validation.pk,
            "document_id": self.validation_document.pk,
            "package_id": self.marketing_package.pk,
            "operation_id": self.operation.pk,
            "agreement_id": self.operation_agreement.pk,
            "opportunity_id": self.provider_opportunity.pk,
            "object_id": self.agent.pk,
            "app_label": "core",
            "model": "agent",
            "pk": self.agent.pk,
        }

    def _sample_value(self, param_name):
        mapping = self._kwargs_for_names()
        return mapping.get(param_name, self.agent.pk)

    def _iter_urlpatterns(self, patterns, prefix=""):
        for pat in patterns:
            if isinstance(pat, URLResolver):
                new_prefix = prefix + pat.pattern.regex.pattern.replace("^", "").replace("$", "")
                yield from self._iter_urlpatterns(pat.url_patterns, prefix=new_prefix)
            elif isinstance(pat, URLPattern) and pat.name:
                yield pat

    def test_all_urls_render(self):
        token = sesame.utils.get_token(self.user)

        tested = []
        for pat in self._iter_urlpatterns(get_resolver().url_patterns):
            try:
                kw = {}
                for name in pat.pattern.converters.keys():
                    kw[name] = self._sample_value(name)
                url = reverse(pat.name, kwargs=kw) if kw else reverse(pat.name)
            except Exception:
                continue  # skip patterns we cannot reverse automatically

            # add sesame token for sesame-login
            if pat.name == "sesame-login":
                joiner = "&" if "?" in url else "?"
                url = f"{url}{joiner}{sesame_settings.TOKEN_NAME}={token}"

            response = self.client.get(url, follow=False)
            tested.append((url, response.status_code))
            self.assertLess(
                response.status_code,
                500,
                msg=f"GET {url} returned {response.status_code}",
            )

        self.assertGreater(len(tested), 0, "No URLs were exercised")
