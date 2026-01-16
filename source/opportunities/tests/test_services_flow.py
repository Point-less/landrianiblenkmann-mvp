from __future__ import annotations

import shutil
import tempfile
from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import Currency
from opportunities.models import OperationType
from core.services import (
    CreateAgentService,
    CreateContactService,
    CreatePropertyService,
    LinkContactAgentService,
)
from integrations.models import TokkobrokerProperty
from users.models import Role, RoleMembership
from intentions.services import (
    CreateProviderIntentionService,
    CreateSeekerIntentionService,
    DeliverValuationService,
    PromoteProviderIntentionService,
    AbandonSeekerIntentionService,
)
from opportunities.models import (
    MarketingPackage,
    MarketingPublication,
    Operation,
    OperationAgreement,
    ProviderOpportunity,
    SeekerOpportunity,
    Validation,
    ValidationDocument,
    ValidationAdditionalDocument,
)
from opportunities.services import (
    CreateAdditionalValidationDocumentService,
    CreateValidationDocumentService,
    CreateOperationAgreementService,
    AgreeOperationAgreementService,
    SignOperationAgreementService,
    CreateSeekerOpportunityService,
    OperationCloseService,
    OperationLoseService,
    OperationReinforceService,
    ReviewValidationDocumentService,
    ValidationAcceptService,
    ValidationPresentService,
    MarketingPackageReleaseService,
)
from utils.models import FSMStateTransition


@override_settings(BYPASS_SERVICE_AUTH_FOR_TESTS=True)
class IntentionFlowServiceTests(TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self._temp_media = tempfile.mkdtemp()
        self.addCleanup(self._cleanup_media)
        self._media_override = override_settings(MEDIA_ROOT=self._temp_media)
        self._media_override.enable()

        self.currency = Currency.objects.create(code="USD", name="US Dollar", symbol="$")
        from opportunities.models import ValidationDocumentType
        for code, label, required in (
            ("owner_id", "DNI PROPIETARIO", True),
            ("deed", "ESCRITURA", True),
            ("sale_authorization", "AUTORIZACION DE VENTA", True),
            ("domain_report", "INFORME DE DOMINIO", True),
            ("other", "OTRO DOCUMENTO", False),
        ):
            ValidationDocumentType.objects.update_or_create(
                code=code,
                defaults={"label": label, "required": required, "accepted_formats": [".pdf"]},
            )
        self.reviewer = get_user_model().objects.create_user(username="reviewer", email="reviewer@example.com")
        self.agent = CreateAgentService.call(first_name="Alice", last_name="Agent", email="alice@example.com")
        agent_ct = ContentType.objects.get_for_model(self.agent.__class__)
        agent_role, _ = Role.objects.get_or_create(slug="agent", defaults={"name": "Agent", "profile_content_type": agent_ct})
        self.owner = CreateContactService.call(first_name="Oscar", last_name="Owner", email="owner@example.com")
        self.seeker_contact = CreateContactService.call(
            first_name="Stella", last_name="Seeker", email="stella@example.com"
        )
        RoleMembership.objects.create(user=self.reviewer, role=agent_role, profile=self.agent)
        self.operation_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})
        self.property = CreatePropertyService.call(name="Ocean View Loft")
        LinkContactAgentService.call(contact=self.owner, agent=self.agent)
        LinkContactAgentService.call(contact=self.seeker_contact, agent=self.agent)

    def _create_provider_opportunity(self, *, tokkobroker_property=None):
        if tokkobroker_property is None:
            tokkobroker_property = TokkobrokerProperty.objects.create(
                tokko_id=99999,
                ref_code="AUTO-REF-99999",
            )
        provider_intention = CreateProviderIntentionService.call(
            owner=self.owner,
            agent=self.agent,
            property=self.property,
            operation_type=self.operation_type,
            notes="Initial walkthrough pending",
        )
        DeliverValuationService.call(
            intention=provider_intention,
            currency=self.currency,
            notes="Comparable units closed last quarter",
            test_value=Decimal("940000"),
            close_value=Decimal("930000"),
        )
        provider_opportunity = PromoteProviderIntentionService.call(
            intention=provider_intention,
            marketing_package_data={},
            gross_commission_pct=Decimal("0.05"),
            tokkobroker_property=tokkobroker_property,
            listing_kind=ProviderOpportunity.ListingKind.EXCLUSIVE,
            contract_expires_on=date.today(),
        )
        validation = Validation.objects.get(opportunity=provider_opportunity)
        return provider_opportunity, validation, provider_intention

    def test_transition_records_actor_from_service_context(self):
        intention = CreateProviderIntentionService.call(
            owner=self.owner,
            agent=self.agent,
            property=self.property,
            operation_type=self.operation_type,
            notes="Actor tracing",
        )

        DeliverValuationService.call(
            intention=intention,
            currency=self.currency,
            notes="With actor",
            actor=self.reviewer,
            test_value=Decimal("940000"),
            close_value=Decimal("930000"),
        )

        transition = intention.state_transitions.filter(
            to_state=intention.State.VALUATED,
            state_field="state",
        ).order_by("-occurred_at", "-id").first()

        self.assertIsNotNone(transition, "transition should be recorded")
        self.assertEqual(transition.actor, self.reviewer)

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
        required_types = validation.required_document_types().values_list("id", flat=True)
        for document in validation.documents.filter(document_type_id__in=required_types, status=ValidationDocument.Status.PENDING):
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
        self.assertEqual(marketing_package.state, MarketingPublication.State.PREPARING)

        self._upload_required_documents(validation)

        extra_document = CreateAdditionalValidationDocumentService.call(
            validation=validation,
            observations="Mandate",
            document=SimpleUploadedFile("mandate.pdf", b"pdf"),
            uploaded_by=self.reviewer,
        )

        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        validation.refresh_from_db()
        self.assertEqual(validation.state, Validation.State.PRESENTED)
        self._review_required_documents(validation)
        extra_document.refresh_from_db()
        self.assertEqual(extra_document.validation, validation)

        ValidationAcceptService.call(validation=validation)
        provider_opportunity.refresh_from_db()
        validation.refresh_from_db()
        self.assertEqual(provider_opportunity.state, ProviderOpportunity.State.MARKETING)
        marketing_package.refresh_from_db()
        self.assertEqual(marketing_package.state, MarketingPublication.State.PREPARING)

        seeker_intention = CreateSeekerIntentionService.call(
            contact=self.seeker_contact,
            agent=self.agent,
            operation_type=self.operation_type,
            budget_min=Decimal("900000"),
            budget_max=Decimal("980000"),
            currency=self.currency,
            desired_features={"bedrooms": 3},
            notes="Looking for turnkey units",
        )

        seeker_opportunity = CreateSeekerOpportunityService.call(
            intention=seeker_intention,
            gross_commission_pct=Decimal("0.03"),
        )
        self.assertEqual(seeker_opportunity.state, SeekerOpportunity.State.MATCHING)

        agreement = CreateOperationAgreementService.call(
            provider_opportunity=provider_opportunity,
            seeker_opportunity=seeker_opportunity,
            initial_offered_amount=Decimal("930000"),
            actor=self.reviewer,
        )
        if agreement.state == OperationAgreement.State.PENDING:
            AgreeOperationAgreementService.call(agreement=agreement)
        _, operation = SignOperationAgreementService.call(
            agreement=agreement,
            signed_document=SimpleUploadedFile("signed.pdf", b"pdf content"),
            reserve_amount=Decimal("20000"),
            reserve_deadline=date.today(),
            currency=self.currency,
            notes="Initial reservation",
        )
        self.assertEqual(operation.state, Operation.State.OFFERED)
        seeker_opportunity.refresh_from_db()
        self.assertEqual(seeker_opportunity.state, SeekerOpportunity.State.NEGOTIATING)
        marketing_package.refresh_from_db()
        self.assertEqual(marketing_package.state, MarketingPublication.State.PREPARING)
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
        abandon_intention = CreateSeekerIntentionService.call(
            contact=self.seeker_contact,
            agent=self.agent,
            operation_type=self.operation_type,
            currency=self.currency,
            budget_min=Decimal("500000"),
            budget_max=Decimal("550000"),
        )
        with self.subTest("abandon seeker intention"):
            AbandonSeekerIntentionService.call(intention=abandon_intention, reason="Shifted priorities")
            self.assertEqual(abandon_intention.state, abandon_intention.State.ABANDONED)

    def test_operation_loss_resets_seeker_to_matching(self):
        provider_opportunity, validation, _ = self._create_provider_opportunity()

        self._upload_required_documents(validation)
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        self._review_required_documents(validation)
        ValidationAcceptService.call(validation=validation)
        provider_opportunity.refresh_from_db()

        seeker_intention = CreateSeekerIntentionService.call(
            contact=self.seeker_contact,
            agent=self.agent,
            operation_type=self.operation_type,
            budget_min=Decimal("900000"),
            budget_max=Decimal("980000"),
            currency=self.currency,
            desired_features={"bedrooms": 3},
            notes="Looking for turnkey units",
        )

        seeker_opportunity = CreateSeekerOpportunityService.call(
            intention=seeker_intention,
            gross_commission_pct=Decimal("0.03"),
        )

        agreement = CreateOperationAgreementService.call(
            provider_opportunity=provider_opportunity,
            seeker_opportunity=seeker_opportunity,
            initial_offered_amount=Decimal("930000"),
            actor=self.reviewer,
        )
        if agreement.state == OperationAgreement.State.PENDING:
            AgreeOperationAgreementService.call(agreement=agreement)
        _, operation = SignOperationAgreementService.call(
            agreement=agreement,
            signed_document=SimpleUploadedFile("signed.pdf", b"pdf content"),
            reserve_amount=Decimal("20000"),
            reserve_deadline=date.today(),
            currency=self.currency,
            notes="Initial reservation",
        )

        OperationLoseService.call(operation=operation, lost_reason="Price too high")

        operation.refresh_from_db()
        seeker_opportunity.refresh_from_db()

        self.assertEqual(operation.state, Operation.State.LOST)
        self.assertEqual(seeker_opportunity.state, SeekerOpportunity.State.MATCHING)
        self.assertEqual(operation.lost_reason, "Price too high")

    def test_operation_loss_keeps_negotiating_if_other_active_operations_exist(self):
        provider_opportunity, validation, _ = self._create_provider_opportunity()
        self._upload_required_documents(validation)
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        self._review_required_documents(validation)
        ValidationAcceptService.call(validation=validation)
        provider_opportunity.refresh_from_db()

        second_property = CreatePropertyService.call(name="Skyline Loft")
        second_intention = CreateProviderIntentionService.call(
            owner=self.owner,
            agent=self.agent,
            property=second_property,
            operation_type=self.operation_type,
            notes="Second listing",
        )
        DeliverValuationService.call(
            intention=second_intention,
            currency=self.currency,
            notes="Downtown comps",
            test_value=Decimal("840000"),
            close_value=Decimal("830000"),
        )
        second_provider_opportunity = PromoteProviderIntentionService.call(
            intention=second_intention,
            marketing_package_data={},
            gross_commission_pct=Decimal("0.05"),
            tokkobroker_property=TokkobrokerProperty.objects.create(tokko_id=88888, ref_code="AUTO-REF-88888"),
            contract_expires_on=date.today(),
        )
        second_validation = Validation.objects.get(opportunity=second_provider_opportunity)
        self._upload_required_documents(second_validation)
        ValidationPresentService.call(validation=second_validation, reviewer=self.agent)
        self._review_required_documents(second_validation)
        ValidationAcceptService.call(validation=second_validation)
        second_provider_opportunity.refresh_from_db()

        seeker_intention = CreateSeekerIntentionService.call(
            contact=self.seeker_contact,
            agent=self.agent,
            operation_type=self.operation_type,
            budget_min=Decimal("900000"),
            budget_max=Decimal("980000"),
            currency=self.currency,
            desired_features={"bedrooms": 3},
            notes="Looking for turnkey units",
        )

        seeker_opportunity = CreateSeekerOpportunityService.call(
            intention=seeker_intention,
            gross_commission_pct=Decimal("0.03"),
        )

        agreement = CreateOperationAgreementService.call(
            provider_opportunity=provider_opportunity,
            seeker_opportunity=seeker_opportunity,
            initial_offered_amount=Decimal("930000"),
            actor=self.reviewer,
        )
        if agreement.state == OperationAgreement.State.PENDING:
            AgreeOperationAgreementService.call(agreement=agreement)
        _, primary_operation = SignOperationAgreementService.call(
            agreement=agreement,
            signed_document=SimpleUploadedFile("signed.pdf", b"pdf content"),
            reserve_amount=Decimal("20000"),
            reserve_deadline=date.today(),
            currency=self.currency,
            notes="Initial reservation",
        )

        agreement_2 = CreateOperationAgreementService.call(
            provider_opportunity=second_provider_opportunity,
            seeker_opportunity=seeker_opportunity,
            initial_offered_amount=Decimal("930000"),
            actor=self.reviewer,
        )
        if agreement_2.state == OperationAgreement.State.PENDING:
            AgreeOperationAgreementService.call(agreement=agreement_2)
        _, secondary_operation = SignOperationAgreementService.call(
            agreement=agreement_2,
            signed_document=SimpleUploadedFile("signed.pdf", b"pdf content"),
            reserve_amount=Decimal("15000"),
            reserve_deadline=date.today(),
            currency=self.currency,
            notes="Backup offer",
        )

        OperationLoseService.call(operation=primary_operation, lost_reason="Negotiations failed")

        seeker_opportunity.refresh_from_db()
        primary_operation.refresh_from_db()
        secondary_operation.refresh_from_db()

        self.assertEqual(primary_operation.state, Operation.State.LOST)
        self.assertEqual(seeker_opportunity.state, SeekerOpportunity.State.NEGOTIATING)
        self.assertIn(secondary_operation.state, [Operation.State.OFFERED, Operation.State.REINFORCED])

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

    def test_document_upload_allowed_while_presented(self):
        provider_opportunity, validation, _ = self._create_provider_opportunity()
        self._upload_required_documents(validation)
        ValidationPresentService.call(validation=validation, reviewer=self.agent)

        late_document = CreateAdditionalValidationDocumentService.call(
            validation=validation,
            document=SimpleUploadedFile("late.pdf", b"data"),
            uploaded_by=self.reviewer,
        )

        late_document.refresh_from_db()
        self.assertEqual(late_document.validation, validation)

    def test_document_upload_blocked_after_approval(self):
        provider_opportunity, validation, _ = self._create_provider_opportunity()
        self._upload_required_documents(validation)
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        self._review_required_documents(validation)
        ValidationAcceptService.call(validation=validation)

        with self.assertRaises(ValidationError):
            CreateValidationDocumentService.call(
                validation=validation,
                document_type="other",
                document=SimpleUploadedFile("late.pdf", b"data"),
                uploaded_by=self.reviewer,
            )

    def test_custom_document_upload_no_type_required(self):
        _, validation, _ = self._create_provider_opportunity()

        custom_doc = CreateAdditionalValidationDocumentService.call(
            validation=validation,
            document=SimpleUploadedFile("custom.pdf", b"data"),
            observations="Photos from visit",
            uploaded_by=self.reviewer,
        )

        custom_doc.refresh_from_db()
        self.assertIsInstance(custom_doc, ValidationAdditionalDocument)
        self.assertEqual(custom_doc.validation, validation)
        self.assertEqual(custom_doc.observations, "Photos from visit")
        self.assertEqual(custom_doc.uploaded_by, self.reviewer)

    def test_custom_document_upload_blocked_after_approval(self):
        _, validation, _ = self._create_provider_opportunity()
        self._upload_required_documents(validation)
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        self._review_required_documents(validation)
        ValidationAcceptService.call(validation=validation)

        with self.assertRaises(ValidationError):
            CreateAdditionalValidationDocumentService.call(
                validation=validation,
                document=SimpleUploadedFile("late.pdf", b"data"),
                uploaded_by=self.reviewer,
            )

    def test_additional_count_includes_custom_documents(self):
        _, validation, _ = self._create_provider_opportunity()

        # two custom documents
        CreateAdditionalValidationDocumentService.call(
            validation=validation,
            document=SimpleUploadedFile("custom1.pdf", b"data"),
            uploaded_by=self.reviewer,
        )
        CreateAdditionalValidationDocumentService.call(
            validation=validation,
            document=SimpleUploadedFile("custom2.pdf", b"data"),
            uploaded_by=self.reviewer,
        )

        summary = validation.document_status_summary()
        self.assertEqual(summary["additional"], 2)

    def test_promote_with_tokkobroker_property_and_uniqueness(self):
        tokko_property = TokkobrokerProperty.objects.create(tokko_id=12345, ref_code="REF-12345")
        provider_opportunity, _, _ = self._create_provider_opportunity(tokkobroker_property=tokko_property)

        provider_opportunity.refresh_from_db()
        tokko_property.refresh_from_db()
        self.assertEqual(provider_opportunity.tokkobroker_property, tokko_property)
        self.assertEqual(tokko_property.provider_opportunity, provider_opportunity)

        secondary_property = CreatePropertyService.call(name="City Loft")
        second_intention = CreateProviderIntentionService.call(
            owner=self.owner,
            agent=self.agent,
            property=secondary_property,
            operation_type=self.operation_type,
        )
        DeliverValuationService.call(
            intention=second_intention,
            currency=self.currency,
            test_value=Decimal("740000"),
            close_value=Decimal("730000"),
        )

        with self.assertRaises(ValidationError):
            PromoteProviderIntentionService.call(
                intention=second_intention,
                marketing_package_data={},
                tokkobroker_property=tokko_property,
                gross_commission_pct=Decimal("0.05"),
                contract_expires_on=date.today(),
                use_atomic=False,
            )

    def _cleanup_media(self):
        self._media_override.disable()
        shutil.rmtree(self._temp_media, ignore_errors=True)
