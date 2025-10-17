from decimal import Decimal

from unittest import mock

from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, transaction
from django.test import TestCase

from core.models import Currency
from opportunities.models import (
    AcquisitionAttempt,
    Agent,
    Appraisal,
    Contact,
    MarketingPackage,
    Operation,
    Opportunity,
    Property,
    Validation,
)
from opportunities.services import (
    AcquisitionAttemptAppraiseService,
    AcquisitionAttemptCaptureService,
    AcquisitionAttemptRejectService,
    BaseService,
    service_atomic,
    CreateOpportunityService,
    MarketingPackageReleaseService,
    MarketingPackageReserveService,
    OperationCloseService,
    OperationLoseService,
    OperationReinforceService,
    OpportunityCloseService,
    OpportunityPublishService,
    OpportunityValidateService,
    ValidationAcceptService,
    ValidationPresentService,
    ValidationRejectService,
)


class OpportunityWorkflowTests(TestCase):
    def setUp(self) -> None:
        self.currency = Currency.objects.create(code="USD", name="US Dollar", symbol="$")
        self.agent = Agent.objects.create(
            first_name="Alice",
            last_name="Agent",
            email="alice.agent@example.com",
        )
        self.owner = Contact.objects.create(
            first_name="Oscar",
            last_name="Owner",
            email="oscar.owner@example.com",
        )
        self.property = Property.objects.create(name="Ocean View Condo")

    def create_opportunity(self, **overrides) -> Opportunity:
        data = {
            "title": "Ocean View Listing",
            "property": self.property,
            "agent": self.agent,
            "owner": self.owner,
            "probability": 25,
            "source": "referral",
        }
        data.update(overrides)
        return CreateOpportunityService.call(
            opportunity_data=data,
            marketing_package_data={"currency": self.currency},
        )

    def test_minimal_happy_path_workflow(self) -> None:
        opportunity = self.create_opportunity()

        opportunity.refresh_from_db()
        self.assertEqual(opportunity.state, Opportunity.State.CAPTURING)

        marketing_package = opportunity.marketing_packages.get()
        self.assertEqual(marketing_package.state, MarketingPackage.State.PREPARING)
        self.assertTrue(marketing_package.is_active)

        validation = opportunity.validations.get()
        self.assertEqual(validation.state, Validation.State.PREPARING)

        acquisition_attempt = AcquisitionAttempt.objects.create(
            opportunity=opportunity,
            assigned_to=self.agent,
        )

        AcquisitionAttemptAppraiseService.call(
            attempt=acquisition_attempt,
            appraisal_data={
                "amount": Decimal("950000"),
                "currency": self.currency,
                "summary": "Initial market assessment",
            },
        )

        acquisition_attempt.refresh_from_db()
        self.assertEqual(acquisition_attempt.state, AcquisitionAttempt.State.NEGOTIATING)

        appraisal = Appraisal.objects.get(attempt=acquisition_attempt)
        self.assertEqual(appraisal.amount, Decimal("950000"))
        self.assertEqual(appraisal.currency, self.currency)

        AcquisitionAttemptCaptureService.call(attempt=acquisition_attempt)
        acquisition_attempt.refresh_from_db()
        self.assertEqual(acquisition_attempt.state, AcquisitionAttempt.State.CLOSED)
        self.assertIsNotNone(acquisition_attempt.closed_at)

        opportunity.refresh_from_db()
        self.assertEqual(opportunity.state, Opportunity.State.VALIDATING)

        validation.refresh_from_db()
        self.assertEqual(validation.state, Validation.State.PREPARING)

        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        validation.refresh_from_db()
        self.assertEqual(validation.state, Validation.State.PRESENTED)
        self.assertEqual(validation.reviewer, self.agent)
        self.assertIsNotNone(validation.presented_at)

        ValidationAcceptService.call(validation=validation)
        validation.refresh_from_db()
        self.assertEqual(validation.state, Validation.State.ACCEPTED)
        self.assertIsNotNone(validation.validated_at)

        opportunity.refresh_from_db()
        self.assertEqual(opportunity.state, Opportunity.State.MARKETING)

        active_package = opportunity.marketing_packages.order_by("-version").first()
        self.assertIsNotNone(active_package)
        self.assertNotEqual(active_package.pk, marketing_package.pk)
        self.assertEqual(active_package.state, MarketingPackage.State.AVAILABLE)
        self.assertTrue(active_package.is_active)

        marketing_package.refresh_from_db()
        self.assertFalse(marketing_package.is_active)

        operation = Operation.objects.create(
            opportunity=opportunity,
            state=Operation.State.OFFERED,
            offered_amount=Decimal("930000"),
            reserve_amount=Decimal("20000"),
            reinforcement_amount=Decimal("15000"),
            currency=self.currency,
        )

        OperationReinforceService.call(operation=operation)
        operation.refresh_from_db()
        self.assertEqual(operation.state, Operation.State.REINFORCED)

        OperationCloseService.call(operation=operation, opportunity=opportunity)
        operation.refresh_from_db()
        self.assertEqual(operation.state, Operation.State.CLOSED)
        self.assertIsNotNone(operation.occurred_at)

        opportunity.refresh_from_db()
        self.assertEqual(opportunity.state, Opportunity.State.CLOSED)

        self.assertTrue(
            opportunity.operations.filter(state=Operation.State.CLOSED).exists()
        )

    def test_acquisition_reject_keeps_opportunity_in_capturing(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(
            opportunity=opportunity,
            assigned_to=self.agent,
        )

        AcquisitionAttemptAppraiseService.call(attempt=attempt)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, AcquisitionAttempt.State.NEGOTIATING)

        AcquisitionAttemptRejectService.call(
            attempt=attempt,
            notes="Owner not ready to proceed",
        )

        attempt.refresh_from_db()
        self.assertEqual(attempt.state, AcquisitionAttempt.State.CLOSED)
        self.assertIn("Owner not ready", attempt.notes)

        opportunity.refresh_from_db()
        self.assertEqual(opportunity.state, Opportunity.State.CAPTURING)

    def test_validation_cycle_reject_and_accept(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)
        AcquisitionAttemptAppraiseService.call(attempt=attempt)
        AcquisitionAttemptCaptureService.call(attempt=attempt)

        validation = opportunity.validations.first()
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        ValidationRejectService.call(validation=validation, notes="Need more documents")

        validation.refresh_from_db()
        self.assertEqual(validation.state, Validation.State.PREPARING)
        self.assertIn("Need more documents", validation.notes)

        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        ValidationAcceptService.call(validation=validation)

        opportunity.refresh_from_db()
        self.assertEqual(opportunity.state, Opportunity.State.MARKETING)

    def test_marketing_reserve_and_release_creates_new_revisions(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)
        AcquisitionAttemptAppraiseService.call(attempt=attempt)
        AcquisitionAttemptCaptureService.call(attempt=attempt)

        validation = opportunity.validations.first()
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        ValidationAcceptService.call(validation=validation)
        opportunity.refresh_from_db()

        active_pkg = opportunity.marketing_packages.order_by("-version").first()
        base_version = active_pkg.version

        reserved_pkg = MarketingPackageReserveService.call(package=active_pkg)
        self.assertNotEqual(reserved_pkg.pk, active_pkg.pk)
        self.assertEqual(reserved_pkg.state, MarketingPackage.State.PAUSED)
        self.assertTrue(reserved_pkg.is_active)
        self.assertEqual(reserved_pkg.version, base_version + 1)

        released_pkg = MarketingPackageReleaseService.call(package=reserved_pkg)
        self.assertNotEqual(released_pkg.pk, reserved_pkg.pk)
        self.assertEqual(released_pkg.state, MarketingPackage.State.AVAILABLE)
        self.assertTrue(released_pkg.is_active)
        self.assertEqual(released_pkg.version, reserved_pkg.version + 1)

        paused_pkg = opportunity.marketing_packages.get(pk=reserved_pkg.pk)
        self.assertFalse(paused_pkg.is_active)

    def test_operation_loss_records_reason_and_closes_opportunity(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)
        AcquisitionAttemptAppraiseService.call(attempt=attempt)
        AcquisitionAttemptCaptureService.call(attempt=attempt)

        validation = opportunity.validations.first()
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        ValidationAcceptService.call(validation=validation)

        operation = Operation.objects.create(
            opportunity=opportunity,
            state=Operation.State.OFFERED,
            offered_amount=Decimal("900000"),
            reserve_amount=Decimal("10000"),
            reinforcement_amount=Decimal("5000"),
            currency=self.currency,
        )

        OperationReinforceService.call(operation=operation)
        OperationLoseService.call(operation=operation, lost_reason="Buyer withdrew")

        operation.refresh_from_db()
        self.assertEqual(operation.state, Operation.State.CLOSED)
        self.assertIn("Buyer withdrew", operation.notes)

        opportunity.refresh_from_db()
        self.assertEqual(opportunity.state, Opportunity.State.CLOSED)

    def test_publish_allowed_without_completed_validation(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)
        AcquisitionAttemptAppraiseService.call(attempt=attempt)
        AcquisitionAttemptCaptureService.call(attempt=attempt)

        validation = opportunity.validations.first()
        self.assertEqual(validation.state, Validation.State.PREPARING)

        OpportunityPublishService.call(opportunity=opportunity)

        opportunity.refresh_from_db()
        self.assertEqual(opportunity.state, Opportunity.State.MARKETING)

        validation.refresh_from_db()
        self.assertEqual(validation.state, Validation.State.PREPARING)

        latest_pkg = opportunity.marketing_packages.order_by("-version").first()
        self.assertEqual(latest_pkg.state, MarketingPackage.State.AVAILABLE)
        self.assertTrue(latest_pkg.is_active)

    def test_reserve_requires_completed_validation(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)
        AcquisitionAttemptAppraiseService.call(attempt=attempt)
        AcquisitionAttemptCaptureService.call(attempt=attempt)

        OpportunityPublishService.call(opportunity=opportunity)
        available_pkg = opportunity.marketing_packages.order_by("-version").first()
        self.assertEqual(available_pkg.state, MarketingPackage.State.AVAILABLE)

        with self.assertRaisesMessage(
            ValidationError,
            "Cannot reserve marketing package before validation is accepted.",
        ):
            MarketingPackageReserveService.call(package=available_pkg)

        transaction.set_rollback(False)

        # No new revision created on failure
        self.assertEqual(
            opportunity.marketing_packages.filter(state=MarketingPackage.State.AVAILABLE).count(),
            1,
        )

    def test_opportunity_validate_requires_capturing_state(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)
        AcquisitionAttemptAppraiseService.call(attempt=attempt)
        AcquisitionAttemptCaptureService.call(attempt=attempt)

        validation = opportunity.validations.first()
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        ValidationAcceptService.call(validation=validation)

        opportunity.refresh_from_db()
        self.assertEqual(opportunity.state, Opportunity.State.MARKETING)

        with self.assertRaises(ValidationError) as exc:
            OpportunityValidateService.call(opportunity=opportunity)
        self.assertIn("Can't switch from state 'marketing'", str(exc.exception))

    def test_opportunity_close_requires_closed_operation(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)
        AcquisitionAttemptAppraiseService.call(attempt=attempt)
        AcquisitionAttemptCaptureService.call(attempt=attempt)

        validation = opportunity.validations.first()
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        ValidationAcceptService.call(validation=validation)

        opportunity.refresh_from_db()
        self.assertEqual(opportunity.state, Opportunity.State.MARKETING)

        with self.assertRaises(ValidationError) as exc:
            OpportunityCloseService.call(opportunity=opportunity)
        self.assertIn("Opportunity cannot be closed without a closed operation.", str(exc.exception))

    def test_acquisition_appraise_requires_current_state(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)
        AcquisitionAttemptAppraiseService.call(attempt=attempt)

        attempt.refresh_from_db()
        self.assertEqual(attempt.state, AcquisitionAttempt.State.NEGOTIATING)

        with self.assertRaises(ValidationError) as exc:
            AcquisitionAttemptAppraiseService.call(attempt=attempt)
        self.assertIn("Can't switch from state", str(exc.exception))

    def test_acquisition_reject_requires_negotiating_state(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)

        with self.assertRaises(ValidationError) as exc:
            AcquisitionAttemptRejectService.call(attempt=attempt)
        self.assertIn("Can't switch from state", str(exc.exception))

    def test_validation_present_requires_preparing_state(self) -> None:
        opportunity = self.create_opportunity()
        validation = opportunity.validations.first()
        ValidationPresentService.call(validation=validation, reviewer=self.agent)

        with self.assertRaises(ValidationError) as exc:
            ValidationPresentService.call(validation=validation, reviewer=self.agent)
        self.assertIn("Can't switch from state", str(exc.exception))

    def test_marketing_release_requires_paused_state(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)
        AcquisitionAttemptAppraiseService.call(attempt=attempt)
        AcquisitionAttemptCaptureService.call(attempt=attempt)

        validation = opportunity.validations.first()
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        ValidationAcceptService.call(validation=validation)

        opportunity.refresh_from_db()
        available_pkg = opportunity.marketing_packages.order_by("-version").first()

        with self.assertRaises(ValidationError) as exc:
            MarketingPackageReleaseService.call(package=available_pkg)
        self.assertIn("Can't switch from state", str(exc.exception))

        # Reset the connection because the failed transition marks the
        # surrounding TestCase transaction for rollback.
        transaction.set_rollback(False)

        reserved_pkg = MarketingPackageReserveService.call(package=available_pkg)
        released_pkg = MarketingPackageReleaseService.call(package=reserved_pkg)
        self.assertEqual(released_pkg.state, MarketingPackage.State.AVAILABLE)

    def test_operation_reinforce_requires_offered_state(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)
        AcquisitionAttemptAppraiseService.call(attempt=attempt)
        AcquisitionAttemptCaptureService.call(attempt=attempt)
        validation = opportunity.validations.first()
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        ValidationAcceptService.call(validation=validation)

        operation = Operation.objects.create(
            opportunity=opportunity,
            state=Operation.State.REINFORCED,
            currency=self.currency,
        )

        with self.assertRaises(ValidationError) as exc:
            OperationReinforceService.call(operation=operation)
        self.assertIn("Can't switch from state", str(exc.exception))

    def test_operation_close_handles_opportunity_transition_failures(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)
        AcquisitionAttemptAppraiseService.call(attempt=attempt)
        AcquisitionAttemptCaptureService.call(attempt=attempt)
        validation = opportunity.validations.first()
        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        ValidationAcceptService.call(validation=validation)

        operation = Operation.objects.create(
            opportunity=opportunity,
            state=Operation.State.REINFORCED,
            currency=self.currency,
        )

        OperationCloseService.call(operation=operation, opportunity=opportunity)
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.state, Opportunity.State.CLOSED)

    def test_service_atomic_respects_existing_transactions(self) -> None:
        with transaction.atomic():
            OpportunityValidateService.call(opportunity=self.create_opportunity())


class BaseServiceTests(TestCase):
    class SampleService(BaseService):
        run_calls = 0

        def run(self, *, value: int) -> int:
            type(self).run_calls += 1
            return value * 2

    def setUp(self) -> None:
        BaseServiceTests.SampleService.run_calls = 0

    def test_base_service_wraps_in_atomic_by_default(self) -> None:
        with mock.patch("opportunities.services.base.service_atomic") as mock_atomic:
            mock_cm = mock.MagicMock()
            mock_atomic.return_value = mock_cm
            mock_cm.__enter__.return_value = None
            mock_cm.__exit__.return_value = False

            result = self.SampleService.call(value=5)

        self.assertEqual(result, 10)
        mock_atomic.assert_called_once_with(DEFAULT_DB_ALIAS)
        self.assertEqual(self.SampleService.run_calls, 1)

    def test_base_service_respects_use_atomic_override(self) -> None:
        with mock.patch("opportunities.services.base.service_atomic") as mock_atomic:
            self.SampleService.call(value=3, use_atomic=False)

        mock_atomic.assert_not_called()
        self.assertEqual(self.SampleService.run_calls, 1)

    def test_service_atomic_savepoint_behavior(self) -> None:
        fake_connection = mock.Mock(in_atomic_block=True)

        with mock.patch("opportunities.services.base.transaction") as mock_tx:
            mock_tx.get_connection.return_value = fake_connection
            mock_cm = mock.MagicMock()
            mock_tx.atomic.return_value = mock_cm
            mock_cm.__enter__.return_value = None
            mock_cm.__exit__.return_value = False

            with service_atomic():
                pass

            mock_tx.atomic.assert_called_once_with(using=DEFAULT_DB_ALIAS, savepoint=False)

        fake_connection.in_atomic_block = False

        with mock.patch("opportunities.services.base.transaction") as mock_tx:
            mock_tx.get_connection.return_value = fake_connection
            mock_cm = mock.MagicMock()
            mock_tx.atomic.return_value = mock_cm
            mock_cm.__enter__.return_value = None
            mock_cm.__exit__.return_value = False

            with service_atomic("alternative"):
                pass

            mock_tx.atomic.assert_called_once_with(using="alternative")
