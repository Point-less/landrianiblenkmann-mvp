from __future__ import annotations

import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import Currency
from core.services import (
    CreateAgentService,
    CreateContactService,
    CreatePropertyService,
    LinkContactAgentService,
)
from integrations.models import TokkobrokerProperty
from intentions.services import (
    AbandonSaleSeekerIntentionService,
    ActivateSaleSeekerIntentionService,
    CreateSaleProviderIntentionService,
    CreateSaleSeekerIntentionService,
    DeliverSaleValuationService,
    MandateSaleSeekerIntentionService,
    PromoteSaleProviderIntentionService,
    StartSaleProviderContractNegotiationService,
)
from opportunities.models import (
    MarketingPackage,
    Operation,
    ProviderOpportunity,
    SeekerOpportunity,
    Validation,
    ValidationDocument,
)
from opportunities.services import (
    CreateValidationDocumentService,
    CreateOperationService,
    CreateSeekerOpportunityService,
    OperationCloseService,
    OperationReinforceService,
    ReviewValidationDocumentService,
    OpportunityValidateService,
    ValidationAcceptService,
    ValidationPresentService,
    MarketingPackageReleaseService,
)
from utils.models import FSMStateTransition


class SaleFlowServiceTests(TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self._temp_media = tempfile.mkdtemp()
        self.addCleanup(self._cleanup_media)
        self._media_override = override_settings(MEDIA_ROOT=self._temp_media)
        self._media_override.enable()

        self.currency = Currency.objects.create(code="USD", name="US Dollar", symbol="$")
        self.reviewer = get_user_model().objects.create_user(username="reviewer")
        self.agent = CreateAgentService.call(first_name="Alice", last_name="Agent", email="alice@example.com")
        self.owner = CreateContactService.call(first_name="Oscar", last_name="Owner", email="owner@example.com")
        self.seeker_contact = CreateContactService.call(
            first_name="Stella", last_name="Seeker", email="stella@example.com"
        )
        self.property = CreatePropertyService.call(name="Ocean View Loft", reference_code="PROP-001")
        LinkContactAgentService.call(contact=self.owner, agent=self.agent)
        LinkContactAgentService.call(contact=self.seeker_contact, agent=self.agent)

    def _create_provider_opportunity(self, *, tokkobroker_property=None):
        provider_intention = CreateSaleProviderIntentionService.call(
            owner=self.owner,
            agent=self.agent,
            property=self.property,
            documentation_notes="Initial walkthrough pending",
        )
        DeliverSaleValuationService.call(
            intention=provider_intention,
            amount=Decimal("950000"),
            currency=self.currency,
            notes="Comparable units closed last quarter",
        )
        StartSaleProviderContractNegotiationService.call(intention=provider_intention)
        provider_opportunity = PromoteSaleProviderIntentionService.call(
            intention=provider_intention,
            marketing_package_data={"currency": self.currency, "price": Decimal("975000")},
            tokkobroker_property=tokkobroker_property,
        )
        validation = Validation.objects.get(opportunity=provider_opportunity)
        OpportunityValidateService.call(opportunity=provider_opportunity)
        return provider_opportunity, validation, provider_intention

    def _upload_required_documents(self, validation: Validation):
        documents = []
        for code, _ in Validation.required_document_choices(include_optional=False):
            document = CreateValidationDocumentService.call(
                validation=validation,
                document_type=code,
                document=SimpleUploadedFile(f"{code}.pdf", b"data"),
                uploaded_by=self.reviewer,
            )
            documents.append(document)
        return documents

    def _review_required_documents(self, validation: Validation):
        for document in validation.documents.filter(document_type__in=Validation.REQUIRED_DOCUMENT_CODES, status=ValidationDocument.Status.PENDING):
            ReviewValidationDocumentService.call(
                document=document,
                action="accept",
                reviewer=self.reviewer,
                comment="Auto-approved for test",
            )

    def test_full_sale_flow_via_services(self) -> None:
        provider_opportunity, validation, provider_intention = self._create_provider_opportunity()
        marketing_package = provider_opportunity.marketing_packages.get()

        self.assertEqual(provider_opportunity.state, ProviderOpportunity.State.VALIDATING)
        self.assertEqual(marketing_package.state, MarketingPackage.State.PREPARING)

        self._upload_required_documents(validation)

        extra_document = CreateValidationDocumentService.call(
            validation=validation,
            document_type=ValidationDocument.DocumentType.OTHER,
            name="Mandate",
            document=SimpleUploadedFile("mandate.pdf", b"pdf"),
            uploaded_by=self.reviewer,
        )

        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        validation.refresh_from_db()
        self.assertEqual(validation.state, Validation.State.PRESENTED)
        self._review_required_documents(validation)
        ReviewValidationDocumentService.call(
            document=extra_document,
            action="accept",
            reviewer=self.reviewer,
            comment="Looks good",
        )

        ValidationAcceptService.call(validation=validation)
        provider_opportunity.refresh_from_db()
        validation.refresh_from_db()
        self.assertEqual(provider_opportunity.state, ProviderOpportunity.State.MARKETING)
        marketing_package.refresh_from_db()
        self.assertEqual(marketing_package.state, MarketingPackage.State.AVAILABLE)

        seeker_intention = CreateSaleSeekerIntentionService.call(
            contact=self.seeker_contact,
            agent=self.agent,
            budget_min=Decimal("900000"),
            budget_max=Decimal("980000"),
            currency=self.currency,
            desired_features={"bedrooms": 3},
            notes="Looking for turnkey units",
        )
        ActivateSaleSeekerIntentionService.call(intention=seeker_intention)
        MandateSaleSeekerIntentionService.call(intention=seeker_intention)

        seeker_opportunity = CreateSeekerOpportunityService.call(intention=seeker_intention)
        self.assertEqual(seeker_opportunity.state, SeekerOpportunity.State.MATCHING)

        operation = CreateOperationService.call(
            provider_opportunity=provider_opportunity,
            seeker_opportunity=seeker_opportunity,
            offered_amount=Decimal("930000"),
            reserve_amount=Decimal("20000"),
            reinforcement_amount=Decimal("15000"),
            currency=self.currency,
            notes="Initial reservation",
        )
        self.assertEqual(operation.state, Operation.State.OFFERED)
        seeker_opportunity.refresh_from_db()
        self.assertEqual(seeker_opportunity.state, SeekerOpportunity.State.NEGOTIATING)
        marketing_package.refresh_from_db()
        self.assertEqual(marketing_package.state, MarketingPackage.State.PAUSED)
        with self.assertRaises(ValidationError):
            MarketingPackageReleaseService.call(package=marketing_package, use_atomic=False)

        OperationReinforceService.call(operation=operation)
        operation.refresh_from_db()
        self.assertEqual(operation.state, Operation.State.REINFORCED)

        OperationCloseService.call(operation=operation)
        operation.refresh_from_db()
        provider_opportunity.refresh_from_db()
        seeker_opportunity.refresh_from_db()

        self.assertEqual(operation.state, Operation.State.CLOSED)
        self.assertIsNotNone(operation.occurred_at)
        self.assertEqual(provider_opportunity.state, ProviderOpportunity.State.CLOSED)
        self.assertEqual(seeker_opportunity.state, SeekerOpportunity.State.CLOSED)

        transition_summary = {
            "provider_intention": provider_intention.state_transitions.count(),
            "seeker_intention": seeker_intention.state_transitions.count(),
            "provider_opportunity": provider_opportunity.state_transitions.count(),
            "seeker_opportunity": seeker_opportunity.state_transitions.count(),
            "operation": operation.state_transitions.count(),
        }
        for label, count in transition_summary.items():
            with self.subTest(object=label):
                self.assertGreaterEqual(count, 1, f"Expected transitions for {label}")

        self.assertTrue(
            FSMStateTransition.objects.filter(
                content_type__model="operation",
                object_id=operation.pk,
                to_state=Operation.State.CLOSED,
            ).exists()
        )

        # ensure we can abandon remaining seeker intents if needed
        abandon_intention = CreateSaleSeekerIntentionService.call(
            contact=self.seeker_contact,
            agent=self.agent,
            currency=self.currency,
            budget_min=Decimal("500000"),
            budget_max=Decimal("550000"),
        )
        with self.subTest("abandon seeker intention"):
            AbandonSaleSeekerIntentionService.call(intention=abandon_intention, reason="Shifted priorities")
            self.assertEqual(abandon_intention.state, abandon_intention.State.ABANDONED)

    def test_validation_present_requires_documents(self):
        provider_opportunity, validation, _ = self._create_provider_opportunity()
        with self.assertRaises(ValidationError):
            ValidationPresentService.call(
                validation=validation,
                reviewer=self.agent,
                use_atomic=False,
            )
        provider_opportunity.refresh_from_db()
        self.assertEqual(provider_opportunity.state, ProviderOpportunity.State.VALIDATING)

    def test_validation_accept_requires_reviewed_documents(self):
        provider_opportunity, validation, _ = self._create_provider_opportunity()
        self._upload_required_documents(validation)
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        with self.assertRaises(ValidationError):
            ValidationAcceptService.call(validation=validation, use_atomic=False)

    def test_document_review_requires_presented_validation(self):
        provider_opportunity, validation, _ = self._create_provider_opportunity()
        required_codes = [code for code, _ in Validation.required_document_choices(include_optional=False)]
        document = CreateValidationDocumentService.call(
            validation=validation,
            document_type=required_codes[0],
            document=SimpleUploadedFile("doc.pdf", b"data"),
            uploaded_by=self.reviewer,
        )
        with self.assertRaises(ValidationError):
            ReviewValidationDocumentService.call(
                document=document,
                action="accept",
                reviewer=self.reviewer,
                comment="Testing",
                use_atomic=False,
            )
        for code in required_codes[1:]:
            CreateValidationDocumentService.call(
                validation=validation,
                document_type=code,
                document=SimpleUploadedFile(f"{code}.pdf", b"data"),
                uploaded_by=self.reviewer,
            )
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        self._review_required_documents(validation)
        ReviewValidationDocumentService.call(
            document=document,
            action="accept",
            reviewer=self.reviewer,
            comment="Now allowed",
        )

    def test_document_upload_only_in_preparing(self):
        provider_opportunity, validation, _ = self._create_provider_opportunity()
        self._upload_required_documents(validation)
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        with self.assertRaises(ValidationError):
            CreateValidationDocumentService.call(
                validation=validation,
                document_type=Validation.required_document_choices(include_optional=False)[0][0],
                document=SimpleUploadedFile("late.pdf", b"data"),
                uploaded_by=self.reviewer,
            )

    def test_promote_with_tokkobroker_property_and_uniqueness(self):
        tokko_property = TokkobrokerProperty.objects.create(tokko_id=12345, ref_code="REF-12345")
        provider_opportunity, _, _ = self._create_provider_opportunity(tokkobroker_property=tokko_property)

        provider_opportunity.refresh_from_db()
        tokko_property.refresh_from_db()
        self.assertEqual(provider_opportunity.tokkobroker_property, tokko_property)
        self.assertEqual(tokko_property.provider_opportunity, provider_opportunity)

        secondary_property = CreatePropertyService.call(name="City Loft", reference_code="PROP-002")
        second_intention = CreateSaleProviderIntentionService.call(
            owner=self.owner,
            agent=self.agent,
            property=secondary_property,
        )
        DeliverSaleValuationService.call(
            intention=second_intention,
            amount=Decimal("750000"),
            currency=self.currency,
        )
        StartSaleProviderContractNegotiationService.call(intention=second_intention)

        with self.assertRaises(ValidationError):
            PromoteSaleProviderIntentionService.call(
                intention=second_intention,
                marketing_package_data={"currency": self.currency},
                tokkobroker_property=tokko_property,
                use_atomic=False,
            )

    def _cleanup_media(self):
        self._media_override.disable()
        shutil.rmtree(self._temp_media, ignore_errors=True)
