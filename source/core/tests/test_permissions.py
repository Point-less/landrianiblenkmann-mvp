import itertools

from django.test import TestCase, Client, override_settings
from django.urls import reverse

from core.models import Agent, Contact, Property
from users.models import User, Role, RoleMembership
from utils.authorization import get_role_profile
from users.management.commands.seed_permissions import Command as SeedPerms
from unittest.mock import patch


class DashboardNavigationTests(TestCase):
    def setUp(self):
        SeedPerms().handle()
        self.client = Client()
        self.viewer = User.objects.create_user(username="viewer_demo", password="viewer123")
        self.agent_user = User.objects.create_user(username="agent_demo", password="agent123")
        self.agent_role = Role.objects.get(slug="agent")
        self.viewer_role = Role.objects.get(slug="viewer")
        agent_profile = Agent.objects.create(first_name="A")
        RoleMembership.objects.create(user=self.agent_user, role=self.agent_role, profile=agent_profile)
        RoleMembership.objects.create(user=self.viewer, role=self.viewer_role)

    def test_viewer_redirects_to_first_allowed_section(self):
        self.client.login(username="viewer_demo", password="viewer123")
        resp = self.client.get(reverse("workflow-dashboard"))
        self.assertEqual(resp.status_code, 302)
        # viewer should land on first allowed section (integration view is allowed; reports also allowed)
        self.assertIn("integration-tokkobroker", resp["Location"])  # first allowed given nav order

    def test_nav_filtered_for_viewer(self):
        self.client.login(username="viewer_demo", password="viewer123")
        resp = self.client.get(reverse("workflow-dashboard-section", kwargs={"section": "reports-operations"}))
        self.assertContains(resp, "Financial & Tax Report")
        self.assertNotContains(resp, "Agents")


class ContactScopingTests(TestCase):
    def setUp(self):
        SeedPerms().handle()
        self.client = Client()
        self.role = Role.objects.get(slug="agent")
        self.agent1 = Agent.objects.create(first_name="Agent1")
        self.agent2 = Agent.objects.create(first_name="Agent2")
        self.user1 = User.objects.create_user(username="agent1", password="pwd")
        self.user2 = User.objects.create_user(username="agent2", password="pwd")
        RoleMembership.objects.create(user=self.user1, role=self.role, profile=self.agent1)
        RoleMembership.objects.create(user=self.user2, role=self.role, profile=self.agent2)
        self.c1 = Contact.objects.create(first_name="C1", last_name="", email="c1@example.com")
        self.c2 = Contact.objects.create(first_name="C2", last_name="", email="c2@example.com")
        self.c1.agents.add(self.agent1)
        self.c2.agents.add(self.agent2)

    def test_contact_query_scopes_to_agent(self):
        self.client.login(username="agent1", password="pwd")
        resp = self.client.get(reverse("workflow-dashboard-section", kwargs={"section": "contacts"}))
        self.assertContains(resp, "C1")
        self.assertNotContains(resp, "C2")

    def test_contact_form_limits_agent_choice(self):
        self.client.login(username="agent1", password="pwd")
        resp = self.client.get(reverse("contact-create"))
        self.assertContains(resp, str(self.agent1))
        self.assertNotContains(resp, str(self.agent2))


@override_settings(TOKKO_DISABLE_SYNC=True)
class IntegrationPermissionsTests(TestCase):
    def setUp(self):
        SeedPerms().handle()
        self.client = Client()
        self.viewer = User.objects.create_user(username="viewer_demo", password="viewer123")
        self.agent_user = User.objects.create_user(username="agent_demo", password="agent123")
        self.manager = User.objects.create_user(username="manager_demo", password="manager123", is_staff=True)
        agent_role = Role.objects.get(slug="agent")
        viewer_role = Role.objects.get(slug="viewer")
        manager_role = Role.objects.get(slug="manager")
        agent_profile = Agent.objects.create(first_name="Agent")
        RoleMembership.objects.create(user=self.agent_user, role=agent_role, profile=agent_profile)
        RoleMembership.objects.create(user=self.viewer, role=viewer_role)
        RoleMembership.objects.create(user=self.manager, role=manager_role)

    def test_integration_view_only_buttons_hidden(self):
        self.client.login(username="agent_demo", password="agent123")
        resp = self.client.get(reverse("workflow-dashboard-section", kwargs={"section": "integration-tokkobroker"}))
        self.assertContains(resp, "Tokkobroker")
        self.assertNotContains(resp, "Sync immediately")

    def test_integration_manage_requires_permission(self):
        with patch("integrations.tokkobroker.fetch_tokkobroker_properties", return_value=None):
            self.client.login(username="agent_demo", password="agent123")
            resp = self.client.post(reverse("integration-tokko-sync-now"))
            self.assertEqual(resp.status_code, 403)

            self.client.login(username="manager_demo", password="manager123")
            resp = self.client.post(reverse("integration-tokko-sync-now"))
            self.assertNotEqual(resp.status_code, 403)


__all__ = []
