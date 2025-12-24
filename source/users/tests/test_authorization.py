from django.core.exceptions import PermissionDenied
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from core.models import Agent, Contact, Property
from opportunities.models import OperationType
from intentions.models import ProviderIntention
from users.models import User, Role, RolePermission, Permission as Perm, RoleMembership
from utils.authorization import (
    Action,
    PROVIDER_INTENTION_VIEW,
    PROVIDER_INTENTION_VIEW_ALL,
    check,
    filter_queryset,
)


class AuthorizationTests(TestCase):
    def setUp(self):
        self.op_type, _ = OperationType.objects.get_or_create(code="sale", defaults={"label": "Sale"})
        self.agent_role = Role.objects.create(
            slug="agent",
            name="Agent",
            profile_content_type=ContentType.objects.get_for_model(Agent),
        )

        self.agent1 = Agent.objects.create(first_name="A1")
        self.agent2 = Agent.objects.create(first_name="A2")
        self.user = User.objects.create_user(username="u1", password="x", email="u1@example.com")
        RoleMembership.objects.create(user=self.user, role=self.agent_role, profile=self.agent1)

        # base permissions
        self.perm_view = Perm.objects.create(code=PROVIDER_INTENTION_VIEW.code)
        self.perm_view_all = Perm.objects.create(code=PROVIDER_INTENTION_VIEW_ALL.code)
        RolePermission.objects.create(role=self.agent_role, permission=self.perm_view, allowed=True)

        owner = Contact.objects.create(first_name="C", email="c@example.com")
        prop = Property.objects.create(name="P")
        self.intention1 = ProviderIntention.objects.create(owner=owner, agent=self.agent1, property=prop, operation_type=self.op_type)
        self.intention2 = ProviderIntention.objects.create(owner=owner, agent=self.agent2, property=prop, operation_type=self.op_type)

    def test_filter_queryset_scopes_to_agent(self):
        qs = ProviderIntention.objects.order_by("id")
        filtered = filter_queryset(self.user, PROVIDER_INTENTION_VIEW, qs, owner_field="agent", view_all_action=PROVIDER_INTENTION_VIEW_ALL)
        self.assertQuerysetEqual(filtered, [self.intention1], ordered=True)

    def test_filter_queryset_view_all(self):
        RolePermission.objects.create(role=self.agent_role, permission=self.perm_view_all, allowed=True)
        qs = ProviderIntention.objects.order_by("id")
        filtered = filter_queryset(self.user, PROVIDER_INTENTION_VIEW, qs, owner_field="agent", view_all_action=PROVIDER_INTENTION_VIEW_ALL)
        self.assertEqual(filtered.count(), 2)

    def test_cache_invalidation_on_role_permission_change(self):
        custom_perm = Perm.objects.create(code="custom.test")
        RolePermission.objects.create(role=self.agent_role, permission=custom_perm, allowed=False)

        with self.assertRaises(PermissionDenied):
            check(self.user, Action("custom.test"))

        # Flip to allowed; signal should clear cache
        rp = RolePermission.objects.get(role=self.agent_role, permission=custom_perm)
        rp.allowed = True
        rp.save()

        # Should now be allowed without manual cache clear
        check(self.user, Action("custom.test"))
