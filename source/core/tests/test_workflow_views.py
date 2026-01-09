from __future__ import annotations

from decimal import Decimal
from datetime import date

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Agent, Contact, Currency, Property
from users.models import Role, RoleMembership
from integrations.models import TokkobrokerProperty
from intentions.services import (
    CreateProviderIntentionService,
    CreateSeekerIntentionService,
    DeliverValuationService,
    PromoteProviderIntentionService,
)
from opportunities.models import OperationAgreement, ProviderOpportunity, Validation, ValidationDocument
from opportunities.services import (
    CreateValidationDocumentService,
    CreateOperationAgreementService,
    AgreeOperationAgreementService,
    SignOperationAgreementService,
    CreateSeekerOpportunityService,
    ReviewValidationDocumentService,
    ValidationAcceptService,
    ValidationPresentService,
)


@override_settings(BYPASS_SERVICE_AUTH_FOR_TESTS=True)
class WorkflowViewSmokeTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self._temp_media = tempfile.mkdtemp()
        self.addCleanup(self._cleanup_media)
        self._media_override = override_settings(MEDIA_ROOT=self._temp_media)
        self._media_override.enable()

        self.admin_password = 'admin'
        self.admin = user_model.objects.create_superuser(
            username='admin', email='admin@example.com', password=self.admin_password
        )
        self.client = Client()
        assert self.client.login(username='admin', password=self.admin_password)

        self.currency = Currency.objects.create(code='USD', name='US Dollar', symbol='$')
        from opportunities.models import ValidationDocumentType
        ValidationDocumentType.objects.update(accepted_formats=[".pdf"])
        self.agent = Agent.objects.create(first_name='Alice', last_name='Agent')
        agent_ct = ContentType.objects.get_for_model(Agent)
        agent_role, _ = Role.objects.get_or_create(slug="agent", defaults={"name": "Agent", "profile_content_type": agent_ct})
        self.owner = Contact.objects.create(first_name='Owner', last_name='One')
        self.seeker_contact = Contact.objects.create(first_name='Buyer', last_name='Beta')
        self.property = Property.objects.create(name='Ocean View Loft')
        from opportunities.models import OperationType
        self.operation_type = OperationType.objects.get(code="sale")
        RoleMembership.objects.create(user=self.admin, role=agent_role, profile=self.agent)
        self.file = SimpleUploadedFile('doc.pdf', b'content')

        self.provider_intention = CreateProviderIntentionService.call(
            owner=self.owner,
            agent=self.agent,
            property=self.property,
            operation_type=self.operation_type,
            notes='Initial notes',
        )
        DeliverValuationService.call(
            intention=self.provider_intention,
            amount=Decimal('950000'),
            currency=self.currency,
            test_value=Decimal('940000'),
            close_value=Decimal('930000'),
        )
        self.tokko_property = TokkobrokerProperty.objects.create(tokko_id=77777, ref_code="AUTO-REF-77777")
        self.provider_opportunity = PromoteProviderIntentionService.call(
            intention=self.provider_intention,
            marketing_package_data={},
            gross_commission_pct=Decimal('0.05'),
            tokkobroker_property=self.tokko_property,
            listing_kind=ProviderOpportunity.ListingKind.EXCLUSIVE,
            contract_expires_on=date.today(),
        )
        self.validation = Validation.objects.get(opportunity=self.provider_opportunity)
        docs = []
        for code, _ in Validation.required_document_choices(include_optional=False):
            docs.append(
                CreateValidationDocumentService.call(
                    validation=self.validation,
                    document_type=code,
                    document=SimpleUploadedFile(f"{code}.pdf", b"doc"),
                    uploaded_by=self.admin,
                )
            )
        ValidationPresentService.call(validation=self.validation, reviewer=self.agent)
        for doc in docs:
            ReviewValidationDocumentService.call(
                document=doc,
                action='accept',
                reviewer=self.admin,
                comment='auto',
            )
        ValidationAcceptService.call(validation=self.validation)
        self.provider_opportunity.refresh_from_db()
        self.marketing_package = self.provider_opportunity.marketing_packages.get()
        self.validation_document = ValidationDocument.objects.create(
            validation=self.validation,
            document_type=ValidationDocumentType.objects.get(code="other"),
            observations='ID Copy',
            document=self.file,
            uploaded_by=self.admin,
        )

        self.seeker_intention = CreateSeekerIntentionService.call(
            contact=self.seeker_contact,
            agent=self.agent,
            operation_type=self.operation_type,
            budget_min=Decimal('900000'),
            budget_max=Decimal('980000'),
            currency=self.currency,
        )
        self.seeker_opportunity = CreateSeekerOpportunityService.call(
            intention=self.seeker_intention,
            gross_commission_pct=Decimal('0.03'),
        )

        agreement = CreateOperationAgreementService.call(
            provider_opportunity=self.provider_opportunity,
            seeker_opportunity=self.seeker_opportunity,
            initial_offered_amount=Decimal('930000'),
            actor=self.admin,
        )
        if agreement.state == OperationAgreement.State.PENDING:
            AgreeOperationAgreementService.call(agreement=agreement)
        _, self.operation = SignOperationAgreementService.call(
            agreement=agreement,
            signed_document=SimpleUploadedFile("signed.pdf", b"pdf content"),
            reserve_amount=Decimal('20000'),
            reserve_deadline=date.today(),
            currency=self.currency,
        )

    def _cleanup_media(self):
        self._media_override.disable()
        shutil.rmtree(self._temp_media, ignore_errors=True)

    def test_all_workflow_views_render(self):
        url_specs = [
            ('workflow-dashboard', {}),
            ('workflow-dashboard-section', {'section': 'agents'}),
            ('workflow-dashboard-section', {'section': 'contacts'}),
            ('workflow-dashboard-section', {'section': 'properties'}),
            ('workflow-dashboard-section', {'section': 'reports-operations'}),
            ('workflow-dashboard-section', {'section': 'provider-intentions'}),
            ('workflow-dashboard-section', {'section': 'provider-opportunities'}),
            ('workflow-dashboard-section', {'section': 'marketing-publications'}),
            ('workflow-dashboard-section', {'section': 'provider-validations'}),
            ('workflow-dashboard-section', {'section': 'seeker-intentions'}),
            ('workflow-dashboard-section', {'section': 'seeker-opportunities'}),
            ('workflow-dashboard-section', {'section': 'operations'}),
            ('workflow-dashboard-section', {'section': 'integration-tokkobroker'}),
            ('workflow-dashboard-section', {'section': 'integration-zonaprop'}),
            ('workflow-dashboard-section', {'section': 'integration-meta'}),
            ('agent-create', {}),
            ('contact-create', {}),
            ('property-create', {}),
            ('provider-intention-create', {}),
            ('provider-deliver-valuation', {'intention_id': self.provider_intention.id}),
            ('provider-promote', {'intention_id': self.provider_intention.id}),
            ('provider-withdraw', {'intention_id': self.provider_intention.id}),
            ('seeker-intention-create', {}),
            ('seeker-create-opportunity', {'intention_id': self.seeker_intention.id}),
            ('validation-present', {'validation_id': self.validation.id}),
            ('validation-reject', {'validation_id': self.validation.id}),
            ('validation-accept', {'validation_id': self.validation.id}),
            ('validation-detail', {'validation_id': self.validation.id}),
            ('validation-document-upload', {'validation_id': self.validation.id}),
            ('validation-document-review', {'document_id': self.validation_document.id}),
            ('marketing-publication-create', {'opportunity_id': self.provider_opportunity.id}),
            ('marketing-publication-edit', {'package_id': self.marketing_package.id}),
            ('marketing-publication-activate', {'package_id': self.marketing_package.id}),
            ('marketing-publication-pause', {'package_id': self.marketing_package.id}),
            ('marketing-publication-release', {'package_id': self.marketing_package.id}),

            ('operation-reinforce', {'operation_id': self.operation.id}),
            ('operation-close', {'operation_id': self.operation.id}),
            ('operation-lose', {'operation_id': self.operation.id}),
            ('transition-history', {'app_label': 'intentions', 'model': 'providerintention', 'object_id': self.provider_intention.id}),
        ]

        for name, kwargs in url_specs:
            with self.subTest(url=name):
                url = reverse(name, kwargs=kwargs) if kwargs else reverse(name)
                response = self.client.get(url)
                self.assertEqual(
                    response.status_code,
                    200,
                    msg=f"View '{name}' did not render successfully",
                )
