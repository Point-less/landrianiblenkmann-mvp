from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import Agent, Contact, Property
from opportunities.models import OperationType, ProviderOpportunity, SeekerOpportunity, Operation
from intentions.models import SaleProviderIntention, SaleSeekerIntention
from opportunities.services.agreements import CreateOperationAgreementService, SignOperationAgreementService
from users.models import Role, RoleMembership, User
from users.management.commands.seed_permissions import Command as SeedPerms


class AgreementCreationRulesTests(TestCase):
    def setUp(self):
        SeedPerms().handle()
        self.agent_role = Role.objects.get(slug="agent")
        self.op_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})

        self.agent_seeker = Agent.objects.create(first_name="SeekerAgent")
        self.agent_provider = Agent.objects.create(first_name="ProviderAgent")

        self.user_seeker = User.objects.create_user(username="seeker_agent", password="pwd")
        RoleMembership.objects.create(user=self.user_seeker, role=self.agent_role, profile=self.agent_seeker)

        # provider belongs to other agent
        self.user_provider = User.objects.create_user(username="provider_agent", password="pwd")
        RoleMembership.objects.create(user=self.user_provider, role=self.agent_role, profile=self.agent_provider)

        contact = Contact.objects.create(first_name="Owner", email="o@example.com")
        seeker_contact = Contact.objects.create(first_name="Buyer", email="b@example.com")
        prop = Property.objects.create(name="Prop")
        from integrations.models import TokkobrokerProperty
        self.tokko = TokkobrokerProperty.objects.create(tokko_id=1, ref_code="REF-1")
        self.currency = None
        from core.models import Currency
        if Currency.objects.exists():
            self.currency = Currency.objects.first()
        else:
            self.currency = Currency.objects.create(code="USD", name="US Dollar")

        sp_int = SaleProviderIntention.objects.create(owner=contact, agent=self.agent_provider, property=prop, operation_type=self.op_type)
        ss_int = SaleSeekerIntention.objects.create(contact=seeker_contact, agent=self.agent_seeker, operation_type=self.op_type, budget_max=Decimal("200000"), currency=self.currency)

        self.provider_opp = ProviderOpportunity.objects.create(source_intention=sp_int, tokkobroker_property=self.tokko)
        self.provider_opp.state = ProviderOpportunity.State.MARKETING
        self.provider_opp.save(update_fields=["state"])
        self.seeker_opp = SeekerOpportunity.objects.create(source_intention=ss_int)

    def test_actor_must_be_seeker_agent(self):
        other_user = self.user_provider
        with self.assertRaises(ValidationError):
            CreateOperationAgreementService(actor=other_user)(
                provider_opportunity=self.provider_opp,
                seeker_opportunity=self.seeker_opp,
                initial_offered_amount=Decimal("100"),
            )

    def test_provider_must_be_other_agent(self):
        # Make provider opp belong to same agent
        self.provider_opp.source_intention.agent = self.agent_seeker
        self.provider_opp.source_intention.save(update_fields=["agent"])
        with self.assertRaises(ValidationError):
            CreateOperationAgreementService(actor=self.user_seeker)(
                provider_opportunity=self.provider_opp,
                seeker_opportunity=self.seeker_opp,
                initial_offered_amount=Decimal("100"),
            )

    def test_initial_offer_stored(self):
        agreement = CreateOperationAgreementService(actor=self.user_seeker)(
            provider_opportunity=self.provider_opp,
            seeker_opportunity=self.seeker_opp,
            initial_offered_amount=Decimal("150000"),
        )
        self.assertEqual(agreement.initial_offered_amount, Decimal("150000"))

        # move to AGREED state then sign
        from opportunities.services.agreements import AgreeOperationAgreementService
        AgreeOperationAgreementService(actor=self.user_seeker)(agreement=agreement)

        op = SignOperationAgreementService(actor=self.user_seeker)(
            agreement=agreement,
            signed_document="dummy.pdf",
            reserve_amount=Decimal("5000"),
            reserve_deadline="2025-12-31",
            currency=self.currency,
        )[1]
        self.assertEqual(op.initial_offered_amount, Decimal("150000"))


__all__ = []
