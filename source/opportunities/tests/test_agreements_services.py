from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.models import Agent, Contact, Currency, Property
from integrations.models import TokkobrokerProperty
from intentions.models import ProviderIntention, SeekerIntention
from opportunities.models import OperationAgreement, OperationType, ProviderOpportunity, SeekerOpportunity, Validation
from opportunities.services.agreements import (
    AgreeOperationAgreementService,
    CancelOperationAgreementService,
    CreateOperationAgreementService,
    RevokeOperationAgreementService,
    SignOperationAgreementService,
)


@override_settings(BYPASS_SERVICE_AUTH_FOR_TESTS=True)
class AgreementServiceTests(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(code="USD", name="US Dollar")
        self.op_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})

        self.agent = Agent.objects.create(first_name="Alice", last_name="Agent")
        self.agent_other = Agent.objects.create(first_name="Bob", last_name="Other")
        self.contact = Contact.objects.create(first_name="Owner", last_name="One", email="owner@example.com")
        self.contact_buyer = Contact.objects.create(first_name="Buyer", last_name="One", email="buyer@example.com")
        self.property = Property.objects.create(name="123 Main")
        self.tokko = TokkobrokerProperty.objects.create(tokko_id=1, ref_code="TK1")

        self.provider_intention = ProviderIntention.objects.create(
            owner=self.contact,
            agent=self.agent,
            property=self.property,
            operation_type=self.op_type,
        )
        self.seeker_intention = SeekerIntention.objects.create(
            contact=self.contact_buyer,
            agent=self.agent,  # same agent for default happy path
            operation_type=self.op_type,
            currency=self.currency,
            budget_min=Decimal("100000"),
            budget_max=Decimal("150000"),
        )

        self.provider_opportunity = ProviderOpportunity.objects.create(
            source_intention=self.provider_intention,
            tokkobroker_property=self.tokko,
            state=ProviderOpportunity.State.MARKETING,
        )
        self.seeker_opportunity = SeekerOpportunity.objects.create(
            source_intention=self.seeker_intention,
            state=SeekerOpportunity.State.MATCHING,
        )

        Validation.objects.create(opportunity=self.provider_opportunity, state=Validation.State.APPROVED)

    def test_create_agreement_requires_actor_is_seeker_agent(self):
        service = CreateOperationAgreementService(actor=None)
        with self.assertRaisesMessage(ValidationError, "represent the seeker"):
            service(
                provider_opportunity=self.provider_opportunity,
                seeker_opportunity=self.seeker_opportunity,
                initial_offered_amount=Decimal("120000"),
            )

    def test_create_agreement_happy_path_auto_agree_when_same_agent(self):
        service = CreateOperationAgreementService(actor=self._actor_user(self.agent))
        agreement = service(
            provider_opportunity=self.provider_opportunity,
            seeker_opportunity=self.seeker_opportunity,
            initial_offered_amount=Decimal("120000"),
        )
        self.assertEqual(agreement.state, OperationAgreement.State.AGREED)

    def test_create_agreement_blocks_existing_active(self):
        service = CreateOperationAgreementService(actor=self._actor_user(self.agent))
        service(
            provider_opportunity=self.provider_opportunity,
            seeker_opportunity=self.seeker_opportunity,
            initial_offered_amount=Decimal("120000"),
        )

        with self.assertRaisesMessage(ValidationError, "active agreement"):
            service(
                provider_opportunity=self.provider_opportunity,
                seeker_opportunity=self.seeker_opportunity,
                initial_offered_amount=Decimal("120000"),
            )

    def test_agree_transition(self):
        agreement = OperationAgreement.objects.create(
            provider_opportunity=self.provider_opportunity,
            seeker_opportunity=self.seeker_opportunity,
            initial_offered_amount=Decimal("120000"),
        )
        svc = AgreeOperationAgreementService(actor=None)
        svc(agreement=agreement)
        self.assertEqual(agreement.state, OperationAgreement.State.AGREED)

    def test_revoke_from_agreed(self):
        agreement = OperationAgreement.objects.create(
            provider_opportunity=self.provider_opportunity,
            seeker_opportunity=self.seeker_opportunity,
            initial_offered_amount=Decimal("120000"),
            state=OperationAgreement.State.AGREED,
        )
        svc = RevokeOperationAgreementService(actor=None)
        svc(agreement=agreement)
        self.assertEqual(agreement.state, OperationAgreement.State.PENDING)

    def test_cancel_from_agreed(self):
        agreement = OperationAgreement.objects.create(
            provider_opportunity=self.provider_opportunity,
            seeker_opportunity=self.seeker_opportunity,
            initial_offered_amount=Decimal("120000"),
            state=OperationAgreement.State.AGREED,
        )
        svc = CancelOperationAgreementService(actor=None)
        svc(agreement=agreement, reason="Buyer withdrew")
        self.assertEqual(agreement.state, OperationAgreement.State.CANCELLED)
        self.assertIn("Buyer withdrew", agreement.cancellation_reason)

    def test_sign_creates_operation(self):
        agreement = OperationAgreement.objects.create(
            provider_opportunity=self.provider_opportunity,
            seeker_opportunity=self.seeker_opportunity,
            initial_offered_amount=Decimal("120000"),
            state=OperationAgreement.State.AGREED,
        )

        svc = SignOperationAgreementService(actor=None)
        agreement, operation = svc(
            agreement=agreement,
            signed_document=None,
            reserve_amount=Decimal("5000"),
            reserve_deadline=date.today(),
            currency=self.currency,
        )

        self.assertEqual(agreement.state, OperationAgreement.State.SIGNED)
        self.assertEqual(operation.agreement, agreement)
        self.assertEqual(operation.currency, self.currency)

    def _actor_user(self, agent: Agent):
        from django.contrib.auth import get_user_model
        from django.contrib.contenttypes.models import ContentType
        from users.models import Role, RoleMembership

        User = get_user_model()
        user = User.objects.create_user(username=f"agent_{agent.pk}", password="pass", email=f"a{agent.pk}@x.com")
        ct = ContentType.objects.get_for_model(Agent)
        role = Role.objects.create(slug="agent", name="Agent", profile_content_type=ct)
        RoleMembership.objects.create(user=user, role=role, profile=agent)
        return user
