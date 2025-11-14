from decimal import Decimal

from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, transaction
from django.test import RequestFactory, TestCase

from core.models import Agent, Contact, ContactAgentRelationship, Currency, Property, TokkobrokerProperty
from opportunities.admin import TokkobrokerPropertyAdmin
from opportunities.models import (
    AcquisitionAttempt,
    Appraisal,
    MarketingPackage,
    Operation,
    Opportunity,
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
from core.tasks import sync_tokkobroker_registry
from utils.services import ServiceInvoker, for_actor


class ActorEchoService(BaseService):
    def run(self, *, actor):
        return actor


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

        validation = opportunity.validations.get()
        self.assertEqual(validation.state, Validation.State.PREPARING)

        acquisition_attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)

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
        self.assertIsNotNone(validation.presented_at)

        ValidationAcceptService.call(validation=validation)
        validation.refresh_from_db()
        self.assertEqual(validation.state, Validation.State.ACCEPTED)
        self.assertIsNotNone(validation.validated_at)

        opportunity.refresh_from_db()
        self.assertEqual(opportunity.state, Opportunity.State.MARKETING)

        active_package = opportunity.marketing_packages.order_by("-created_at").first()
        self.assertIsNotNone(active_package)
        self.assertEqual(active_package.pk, marketing_package.pk)
        self.assertEqual(active_package.state, MarketingPackage.State.AVAILABLE)

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
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)

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

        active_pkg = opportunity.marketing_packages.order_by("-created_at").first()

        reserved_pkg = MarketingPackageReserveService.call(package=active_pkg)
        self.assertEqual(reserved_pkg.pk, active_pkg.pk)
        self.assertEqual(reserved_pkg.state, MarketingPackage.State.PAUSED)

        released_pkg = MarketingPackageReleaseService.call(package=reserved_pkg)
        self.assertEqual(released_pkg.pk, reserved_pkg.pk)
        self.assertEqual(released_pkg.state, MarketingPackage.State.AVAILABLE)

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

        latest_pkg = opportunity.marketing_packages.order_by("-created_at").first()
        self.assertEqual(latest_pkg.state, MarketingPackage.State.AVAILABLE)

    def test_reserve_requires_completed_validation(self) -> None:
        opportunity = self.create_opportunity()
        attempt = AcquisitionAttempt.objects.create(opportunity=opportunity)
        AcquisitionAttemptAppraiseService.call(attempt=attempt)
        AcquisitionAttemptCaptureService.call(attempt=attempt)

        OpportunityPublishService.call(opportunity=opportunity)
        available_pkg = opportunity.marketing_packages.order_by("-created_at").first()
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
        available_pkg = opportunity.marketing_packages.order_by("-created_at").first()

        with self.assertRaises(ValidationError) as exc:
            MarketingPackageReleaseService.call(package=available_pkg)
        self.assertIn("Can't switch from state", str(exc.exception))

        # Reset the connection because the failed transition marks the
        # surrounding TestCase transaction for rollback.
        transaction.set_rollback(False)

        reserved_pkg = MarketingPackageReserveService.call(package=available_pkg)
        released_pkg = MarketingPackageReleaseService.call(package=reserved_pkg)
        self.assertEqual(reserved_pkg.pk, available_pkg.pk)
        self.assertEqual(released_pkg.pk, available_pkg.pk)
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
        with mock.patch("utils.services.base.service_atomic") as mock_atomic:
            mock_cm = mock.MagicMock()
            mock_atomic.return_value = mock_cm
            mock_cm.__enter__.return_value = None
            mock_cm.__exit__.return_value = False

            result = self.SampleService.call(value=5)

        self.assertEqual(result, 10)
        mock_atomic.assert_called_once_with(DEFAULT_DB_ALIAS)
        self.assertEqual(self.SampleService.run_calls, 1)

    def test_base_service_respects_use_atomic_override(self) -> None:
        with mock.patch("utils.services.base.service_atomic") as mock_atomic:
            self.SampleService.call(value=3, use_atomic=False)

        mock_atomic.assert_not_called()
        self.assertEqual(self.SampleService.run_calls, 1)

    def test_service_atomic_savepoint_behavior(self) -> None:
        fake_connection = mock.Mock(in_atomic_block=True)

        with mock.patch("utils.services.base.transaction") as mock_tx:
            mock_tx.get_connection.return_value = fake_connection
            mock_cm = mock.MagicMock()
            mock_tx.atomic.return_value = mock_cm
            mock_cm.__enter__.return_value = None
            mock_cm.__exit__.return_value = False

            with service_atomic():
                pass

            mock_tx.atomic.assert_called_once_with(using=DEFAULT_DB_ALIAS, savepoint=False)

        fake_connection.in_atomic_block = False

        with mock.patch("utils.services.base.transaction") as mock_tx:
            mock_tx.get_connection.return_value = fake_connection
            mock_cm = mock.MagicMock()
            mock_tx.atomic.return_value = mock_cm
            mock_cm.__enter__.return_value = None
            mock_cm.__exit__.return_value = False

            with service_atomic("alternative"):
                pass

            mock_tx.atomic.assert_called_once_with(using="alternative")

    def test_actor_is_injected_into_run(self) -> None:
        self.assertEqual(ActorEchoService(actor="alice")(), "alice")
        self.assertEqual(ActorEchoService.call(actor="bob"), "bob")
        service = ActorEchoService()
        self.assertEqual(service(actor="carol"), "carol")


class ServiceInvokerTests(TestCase):
    def test_invoker_binds_actor_to_service_instances(self) -> None:
        invoker = ServiceInvoker(actor="otto")
        instance = invoker.get(CreateOpportunityService)
        self.assertEqual(instance.actor, "otto")

    def test_invoker_call_passes_actor(self) -> None:
        invoker = for_actor("echo-user")
        captured = {}

        def fake_run(self, *, actor):
            captured["actor"] = actor
            return actor

        with mock.patch.object(ActorEchoService, "run", fake_run):
            result = invoker.call(
                f"{ActorEchoService.__module__}.ActorEchoService",
            )

        self.assertEqual(captured["actor"], "echo-user")
        self.assertEqual(result, "echo-user")


class TokkobrokerRegistryTests(TestCase):
    def test_sync_creates_registry_entries(self) -> None:
        payload = {
            "id": 123,
            "ref_code": "ABC123",
            "address": "123 Demo Street",
            "quick_data": {"data": {"created_at": "18-07-2024"}},
        }

        processed = sync_tokkobroker_registry([payload])

        self.assertEqual(processed, 1)
        entry = TokkobrokerProperty.objects.get(tokko_id=123)
        self.assertEqual(entry.ref_code, "ABC123")
        self.assertEqual(entry.address, "123 Demo Street")
        self.assertEqual(entry.tokko_created_at.isoformat(), "2024-07-18")

    def test_admin_action_triggers_sync(self) -> None:
        admin = TokkobrokerPropertyAdmin(TokkobrokerProperty, AdminSite())
        request = RequestFactory().post("/admin/opportunities/tokkobrokerproperty/")

        with (
            mock.patch("opportunities.admin.sync_tokkobroker_registry", return_value=3) as mock_sync,
            mock.patch.object(TokkobrokerPropertyAdmin, "message_user") as mock_message,
        ):
            admin.sync_from_tokkobroker_action(request, TokkobrokerProperty.objects.none())

        mock_sync.assert_called_once_with()
        mock_message.assert_called_once()
