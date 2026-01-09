from __future__ import annotations


from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import Agent, Contact, Property
from intentions.models import ProviderIntention
from intentions.services import CreateProviderIntentionService
from opportunities.models import OperationType


class ProviderIntentionUniquenessTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(first_name="Agent", last_name="One")
        self.owner = Contact.objects.create(first_name="Owner", last_name="One", email="o@example.com")
        self.property = Property.objects.create(name="123 Main")
        self.operation_type = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})[0]

    def test_prevents_duplicate_active_intentions_same_agent_property(self):
        CreateProviderIntentionService.call(
            owner=self.owner,
            agent=self.agent,
            property=self.property,
            operation_type=self.operation_type,
            notes="first",
        )
        with self.assertRaises(ValidationError):
            CreateProviderIntentionService.call(
                owner=self.owner,
                agent=self.agent,
                property=self.property,
                operation_type=self.operation_type,
                notes="duplicate",
            )

    def test_allows_new_after_withdrawn(self):
        intention = CreateProviderIntentionService.call(
            owner=self.owner,
            agent=self.agent,
            property=self.property,
            operation_type=self.operation_type,
            notes="first",
        )
        intention.withdraw(reason=ProviderIntention.WithdrawReason.NO_RESPONSE, notes=None)
        intention.save(update_fields=["state", "withdraw_reason", "updated_at"])

        # Should allow creating a new one after withdrawal
        CreateProviderIntentionService.call(
            owner=self.owner,
            agent=self.agent,
            property=self.property,
            operation_type=self.operation_type,
            notes="second",
        )
