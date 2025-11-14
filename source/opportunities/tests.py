from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from core.models import Currency
from core.services import (
    CreateAgentService,
    CreateContactService,
    CreatePropertyService,
    LinkContactAgentService,
)
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
from opportunities.models import MarketingPackage, Operation, ProviderOpportunity, SeekerOpportunity, Validation
from opportunities.services import (
    CreateOperationService,
    CreateSeekerOpportunityService,
    OperationCloseService,
    OperationReinforceService,
    OpportunityValidateService,
    ValidationAcceptService,
    ValidationPresentService,
)
from utils.models import FSMStateTransition


class SaleFlowServiceTests(TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.currency = Currency.objects.create(code="USD", name="US Dollar", symbol="$")
        self.agent = CreateAgentService.call(first_name="Alice", last_name="Agent", email="alice@example.com")
        self.owner = CreateContactService.call(first_name="Oscar", last_name="Owner", email="owner@example.com")
        self.seeker_contact = CreateContactService.call(
            first_name="Stella", last_name="Seeker", email="stella@example.com"
        )
        self.property = CreatePropertyService.call(name="Ocean View Loft", reference_code="PROP-001")
        LinkContactAgentService.call(contact=self.owner, agent=self.agent)
        LinkContactAgentService.call(contact=self.seeker_contact, agent=self.agent)

    def test_full_sale_flow_via_services(self) -> None:
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
            opportunity_title="Ocean View Exclusive",
            marketing_package_data={"currency": self.currency, "price": Decimal("975000")},
        )
        self.assertEqual(provider_opportunity.state, ProviderOpportunity.State.CAPTURING)
        validation = Validation.objects.get(opportunity=provider_opportunity)
        marketing_package = provider_opportunity.marketing_packages.get()
        self.assertEqual(marketing_package.state, MarketingPackage.State.PREPARING)

        OpportunityValidateService.call(opportunity=provider_opportunity)
        provider_opportunity.refresh_from_db()
        self.assertEqual(provider_opportunity.state, ProviderOpportunity.State.VALIDATING)

        ValidationPresentService.call(validation=validation, reviewer=self.agent)
        validation.refresh_from_db()
        self.assertEqual(validation.state, Validation.State.PRESENTED)

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
