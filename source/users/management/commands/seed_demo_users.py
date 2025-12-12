from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from core.models import Agent
from users.models import Role, RoleMembership


class Command(BaseCommand):
    help = "Create demo users with roles/memberships to exercise permissions. Safe to re-run."

    def handle(self, *args, **options):
        call_command("seed_permissions")

        User = get_user_model()

        agent_ct = ContentType.objects.get_for_model(Agent)
        roles = {r.slug: r for r in Role.objects.filter(slug__in=["admin", "manager", "agent", "viewer"])}

        # Admin user (no profile needed)
        admin_user, _ = User.objects.get_or_create(
            username="admin_demo",
            defaults={"email": "admin@example.com", "is_staff": True, "is_superuser": True},
        )
        admin_user.set_password("admin123")
        admin_user.save()

        # Manager (with agent profile)
        manager_agent, _ = Agent.objects.get_or_create(first_name="Manager", last_name="Demo", email="manager@example.com")
        manager_user, _ = User.objects.get_or_create(
            username="manager_demo",
            defaults={"email": "manager@example.com"},
        )
        manager_user.set_password("manager123")
        manager_user.save()
        RoleMembership.objects.get_or_create(
            user=manager_user,
            role=roles.get("manager"),
            defaults={"profile_content_type": agent_ct, "profile_id": manager_agent.id},
        )

        # Agent
        agent_profile, _ = Agent.objects.get_or_create(first_name="Anna", last_name="Agent", email="agent@example.com")
        agent_user, _ = User.objects.get_or_create(
            username="agent_demo",
            defaults={"email": "agent@example.com"},
        )
        agent_user.set_password("agent123")
        agent_user.save()
        RoleMembership.objects.get_or_create(
            user=agent_user,
            role=roles.get("agent"),
            defaults={"profile_content_type": agent_ct, "profile_id": agent_profile.id},
        )

        # Viewer (no profile)
        viewer_user, _ = User.objects.get_or_create(
            username="viewer_demo",
            defaults={"email": "viewer@example.com"},
        )
        viewer_user.set_password("viewer123")
        viewer_user.save()
        RoleMembership.objects.get_or_create(user=viewer_user, role=roles.get("viewer"))

        self.stdout.write(self.style.SUCCESS("Demo users created/updated. Passwords: admin123 / manager123 / agent123 / viewer123"))
