from __future__ import annotations

from decimal import Decimal

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Agent, Contact, Currency, Property
from intentions.models import SaleProviderIntention, SaleSeekerIntention
from intentions.services import (
    ActivateSaleSeekerIntentionService,
    CreateSaleProviderIntentionService,
    CreateSaleSeekerIntentionService,
    DeliverSaleValuationService,
    MandateSaleSeekerIntentionService,
    PromoteSaleProviderIntentionService,
    StartSaleProviderContractNegotiationService,
)
from opportunities.models import Operation, ProviderOpportunity, Validation, ValidationDocument
from opportunities.services import (
    CreateValidationDocumentService,
    CreateOperationService,
    CreateSeekerOpportunityService,
    OpportunityValidateService,
    ReviewValidationDocumentService,
    ValidationAcceptService,
    ValidationPresentService,
)


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
        self.agent = Agent.objects.create(first_name='Alice', last_name='Agent')
        self.owner = Contact.objects.create(first_name='Owner', last_name='One')
        self.seeker_contact = Contact.objects.create(first_name='Buyer', last_name='Beta')
        self.property = Property.objects.create(name='Ocean View Loft', reference_code='PROP-001')
        self.file = SimpleUploadedFile('doc.pdf', b'content')

        self.provider_intention = CreateSaleProviderIntentionService.call(
            owner=self.owner,
            agent=self.agent,
            property=self.property,
            documentation_notes='Initial notes',
        )
        DeliverSaleValuationService.call(
            intention=self.provider_intention,
            amount=Decimal('950000'),
            currency=self.currency,
        )
        StartSaleProviderContractNegotiationService.call(intention=self.provider_intention)
        self.provider_opportunity = PromoteSaleProviderIntentionService.call(
            intention=self.provider_intention,
            marketing_package_data={'currency': self.currency},
        )
        self.validation = Validation.objects.get(opportunity=self.provider_opportunity)
        OpportunityValidateService.call(opportunity=self.provider_opportunity)
        for code, _ in Validation.required_document_choices(include_optional=False):
            doc = CreateValidationDocumentService.call(
                validation=self.validation,
                document_type=code,
                document=SimpleUploadedFile(f"{code}.pdf", b"doc"),
                uploaded_by=self.admin,
            )
            ReviewValidationDocumentService.call(
                document=doc,
                action='accept',
                reviewer=self.admin,
                comment='auto',
            )
        ValidationPresentService.call(validation=self.validation, reviewer=self.agent)
        ValidationAcceptService.call(validation=self.validation)
        self.provider_opportunity.refresh_from_db()
        self.marketing_package = self.provider_opportunity.marketing_packages.get()
        self.validation_document = ValidationDocument.objects.create(
            validation=self.validation,
            document_type=ValidationDocument.DocumentType.OTHER,
            name='ID Copy',
            document=self.file,
            uploaded_by=self.admin,
        )

        self.seeker_intention = CreateSaleSeekerIntentionService.call(
            contact=self.seeker_contact,
            agent=self.agent,
            budget_min=Decimal('900000'),
            budget_max=Decimal('980000'),
            currency=self.currency,
        )
        ActivateSaleSeekerIntentionService.call(intention=self.seeker_intention)
        MandateSaleSeekerIntentionService.call(intention=self.seeker_intention)
        self.seeker_opportunity = CreateSeekerOpportunityService.call(intention=self.seeker_intention)

        self.operation = CreateOperationService.call(
            provider_opportunity=self.provider_opportunity,
            seeker_opportunity=self.seeker_opportunity,
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
            ('workflow-dashboard-section', {'section': 'provider-intentions'}),
            ('workflow-dashboard-section', {'section': 'provider-opportunities'}),
            ('workflow-dashboard-section', {'section': 'marketing-packages'}),
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
            ('provider-start-contract', {'intention_id': self.provider_intention.id}),
            ('provider-promote', {'intention_id': self.provider_intention.id}),
            ('provider-withdraw', {'intention_id': self.provider_intention.id}),
            ('seeker-intention-create', {}),
            ('seeker-activate', {'intention_id': self.seeker_intention.id}),
            ('seeker-mandate', {'intention_id': self.seeker_intention.id}),
            ('seeker-abandon', {'intention_id': self.seeker_intention.id}),
            ('seeker-create-opportunity', {'intention_id': self.seeker_intention.id}),
            ('provider-opportunity-validate', {'opportunity_id': self.provider_opportunity.id}),
            ('validation-present', {'validation_id': self.validation.id}),
            ('validation-reject', {'validation_id': self.validation.id}),
            ('validation-accept', {'validation_id': self.validation.id}),
            ('validation-document-upload', {'validation_id': self.validation.id}),
            ('validation-document-review', {'document_id': self.validation_document.id}),
            ('marketing-package-create', {'opportunity_id': self.provider_opportunity.id}),
            ('marketing-package-edit', {'package_id': self.marketing_package.id}),
            ('marketing-package-activate', {'package_id': self.marketing_package.id}),
            ('marketing-package-reserve', {'package_id': self.marketing_package.id}),
            ('marketing-package-release', {'package_id': self.marketing_package.id}),
            ('operation-create', {}),
            ('operation-reinforce', {'operation_id': self.operation.id}),
            ('operation-close', {'operation_id': self.operation.id}),
            ('operation-lose', {'operation_id': self.operation.id}),
            ('transition-history', {'app_label': 'intentions', 'model': 'saleproviderintention', 'object_id': self.provider_intention.id}),
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
