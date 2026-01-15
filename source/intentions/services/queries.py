from __future__ import annotations

from core.models import Contact, Agent
from opportunities.models import OperationType
from django.core.exceptions import PermissionDenied

from utils.authorization import AGENT_VIEW_ALL, CONTACT_VIEW, CONTACT_VIEW_ALL, check, filter_queryset, get_role_profile
from utils.services import BaseService


class PrepareProviderIntentionChoicesService(BaseService):
    """Prepare querysets for ProviderIntentionForm."""

    atomic = False

    def run(self, *, actor=None):
        operation_types = OperationType.objects.all()
        owner_qs = Contact.objects.order_by("last_name", "first_name")
        actor_agent = None
        agent_qs = Agent.objects.order_by("last_name", "first_name")
        can_view_all_agents = actor is None

        if actor is not None:
            owner_qs = filter_queryset(
                actor,
                CONTACT_VIEW,
                owner_qs,
                owner_field="agents",
                view_all_action=CONTACT_VIEW_ALL,
            )
            try:
                check(actor, AGENT_VIEW_ALL)
            except PermissionDenied:
                can_view_all_agents = False
            else:
                can_view_all_agents = True

            if not can_view_all_agents:
                actor_agent = get_role_profile(actor, "agent")
                agent_qs = agent_qs.filter(pk=actor_agent.pk)

        return {
            "operation_type_qs": operation_types,
            "owner_qs": owner_qs,
            "agent_qs": agent_qs,
            "actor_agent": actor_agent,
            "can_view_all_agents": can_view_all_agents,
        }


class PrepareSeekerIntentionChoicesService(BaseService):
    """Prepare querysets for SeekerIntentionForm."""

    atomic = False

    def run(self, *, actor=None):
        operation_types = OperationType.objects.all()
        contact_qs = Contact.objects.order_by("last_name", "first_name")
        actor_agent = None
        agent_qs = Agent.objects.order_by("last_name", "first_name")
        can_view_all_agents = actor is None

        if actor is not None:
            contact_qs = filter_queryset(
                actor,
                CONTACT_VIEW,
                contact_qs,
                owner_field="agents",
                view_all_action=CONTACT_VIEW_ALL,
            )
            try:
                check(actor, AGENT_VIEW_ALL)
            except PermissionDenied:
                can_view_all_agents = False
            else:
                can_view_all_agents = True

            if not can_view_all_agents:
                actor_agent = get_role_profile(actor, "agent")
                agent_qs = Agent.objects.filter(pk=actor_agent.pk) if actor_agent else Agent.objects.none()

        return {
            "operation_type_qs": operation_types,
            "contact_qs": contact_qs,
            "agent_qs": agent_qs,
            "actor_agent": actor_agent,
            "can_view_all_agents": can_view_all_agents,
        }


__all__ = [
    "PrepareProviderIntentionChoicesService",
    "PrepareSeekerIntentionChoicesService",
]
