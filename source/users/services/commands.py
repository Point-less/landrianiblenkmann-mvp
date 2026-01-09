from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from core.models import Agent
from users.models import Permission, Role, RoleMembership, RolePermission
from utils.services import BaseService


class BootstrapSuperuserService(BaseService):
    """Create or update the bootstrap superuser."""

    def run(self, *, username: str, email: str, password: str | None):
        user_model = get_user_model()
        existing = user_model.objects.filter(username=username).first()
        if existing:
            if password:
                existing.set_password(password)
            if email:
                existing.email = email
            existing.is_superuser = True
            existing.is_staff = True
            existing.save()
            return existing
        if not password:
            raise ValueError("Password required to create superuser.")
        return user_model.objects.create_superuser(username=username, email=email, password=password)


class SeedPermissionsService(BaseService):
    """Seed canonical roles and permissions."""

    def run(self, *, actions):
        agent_ct = ContentType.objects.get_for_model(Agent)
        roles = {}
        for slug, defaults in [
            ("admin", {"name": "Admin", "profile_content_type": agent_ct}),
            ("manager", {"name": "Manager", "profile_content_type": agent_ct}),
            ("agent", {"name": "Agent", "profile_content_type": agent_ct}),
            ("viewer", {"name": "Viewer", "profile_content_type": agent_ct}),
        ]:
            role, _ = Role.objects.get_or_create(slug=slug, defaults=defaults)
            roles[slug] = role

        perm_map = {}
        for action in actions:
            perm, _ = Permission.objects.get_or_create(code=action.code, defaults={"description": action.code})
            perm_map[action.code] = perm

        role_targets = {
            "admin": list(perm_map.values()),
            "manager": list(perm_map.values()),
            "agent": [p for code, p in perm_map.items() if not code.startswith("user.")],
            "viewer": [p for code, p in perm_map.items() if code.startswith("report.")],
        }

        for slug, perm_list in role_targets.items():
            role = roles[slug]
            target_codes = [p.code for p in perm_list]
            RolePermission.objects.filter(role=role).exclude(permission__code__in=target_codes).delete()
            for perm in perm_list:
                RolePermission.objects.update_or_create(role=role, permission=perm, defaults={"allowed": True})


class SeedDemoUsersService(BaseService):
    """Create demo users/roles for local environments."""

    def run(self):
        user_model = get_user_model()
        agent_ct = ContentType.objects.get_for_model(Agent)
        roles = {r.slug: r for r in Role.objects.filter(slug__in=["admin", "manager", "agent", "viewer"])}

        admin_user, _ = user_model.objects.get_or_create(
            username="admin_demo",
            defaults={"email": "admin@example.com", "is_staff": True, "is_superuser": True},
        )
        admin_user.set_password("admin123")
        admin_user.save()

        manager_agent, _ = Agent.objects.get_or_create(first_name="Manager", last_name="Demo", email="manager@example.com")
        manager_user, _ = user_model.objects.get_or_create(username="manager_demo", defaults={"email": "manager@example.com"})
        manager_user.set_password("manager123")
        manager_user.save()
        RoleMembership.objects.get_or_create(
            user=manager_user,
            role=roles.get("manager"),
            defaults={"profile_content_type": agent_ct, "profile_id": manager_agent.id},
        )

        agent_profile, _ = Agent.objects.get_or_create(first_name="Anna", last_name="Agent", email="agent@example.com")
        agent_user, _ = user_model.objects.get_or_create(username="agent_demo", defaults={"email": "agent@example.com"})
        agent_user.set_password("agent123")
        agent_user.save()
        RoleMembership.objects.get_or_create(
            user=agent_user,
            role=roles.get("agent"),
            defaults={"profile_content_type": agent_ct, "profile_id": agent_profile.id},
        )

        viewer_user, _ = user_model.objects.get_or_create(username="viewer_demo", defaults={"email": "viewer@example.com"})
        viewer_user.set_password("viewer123")
        viewer_user.save()
        RoleMembership.objects.get_or_create(user=viewer_user, role=roles.get("viewer"))


__all__ = [
    "BootstrapSuperuserService",
    "SeedPermissionsService",
    "SeedDemoUsersService",
]
