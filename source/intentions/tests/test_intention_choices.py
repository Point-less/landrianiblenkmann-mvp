from __future__ import annotations

from django.test import TestCase

from core.models import Agent
from intentions.services import PrepareProviderIntentionChoicesService, PrepareSeekerIntentionChoicesService
from users.management.commands.seed_permissions import Command as SeedPerms
from users.models import Role, RoleMembership, User


class IntentionChoicesServiceTests(TestCase):
    def setUp(self):
        SeedPerms().handle()
        self.agent_one = Agent.objects.create(first_name="Agent", last_name="One", email="a1@example.com")
        self.agent_two = Agent.objects.create(first_name="Agent", last_name="Two", email="a2@example.com")
        self.agent_user = User.objects.create_user(username="agent_user", password="pwd", email="agent_user@example.com")
        self.manager_user = User.objects.create_user(
            username="manager_user",
            password="pwd",
            email="manager_user@example.com",
            is_staff=True,
        )
        self.agent_role = Role.objects.get(slug="agent")
        self.manager_role = Role.objects.get(slug="manager")
        RoleMembership.objects.create(user=self.agent_user, role=self.agent_role, profile=self.agent_one)
        RoleMembership.objects.create(user=self.manager_user, role=self.manager_role, profile=self.agent_two)

    def test_agent_only_sees_self_in_provider_choices(self):
        data = PrepareProviderIntentionChoicesService.call(actor=self.agent_user)
        self.assertEqual(list(data["agent_qs"]), [self.agent_one])
        self.assertFalse(data["can_view_all_agents"])

    def test_agent_only_sees_self_in_seeker_choices(self):
        data = PrepareSeekerIntentionChoicesService.call(actor=self.agent_user)
        self.assertEqual(list(data["agent_qs"]), [self.agent_one])
        self.assertFalse(data["can_view_all_agents"])

    def test_manager_sees_all_agents_in_provider_choices(self):
        data = PrepareProviderIntentionChoicesService.call(actor=self.manager_user)
        self.assertCountEqual(list(data["agent_qs"]), [self.agent_one, self.agent_two])
        self.assertTrue(data["can_view_all_agents"])

    def test_manager_sees_all_agents_in_seeker_choices(self):
        data = PrepareSeekerIntentionChoicesService.call(actor=self.manager_user)
        self.assertCountEqual(list(data["agent_qs"]), [self.agent_one, self.agent_two])
        self.assertTrue(data["can_view_all_agents"])


__all__ = []

