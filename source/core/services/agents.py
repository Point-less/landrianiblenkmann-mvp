"""Service objects for agent management."""

from typing import Any

from django.core.exceptions import ValidationError

from core.models import Agent
from utils.services import BaseService
from utils.authorization import AGENT_CREATE, AGENT_UPDATE


class CreateAgentService(BaseService):
    """Register a new sales agent."""

    required_action = AGENT_CREATE

    def run(
        self,
        *,
        first_name: str,
        last_name: str = "",
        email: str | None = None,
        phone_number: str | None = None,
        commission_split: float | None = None,
    ) -> Agent:
        data = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email or "",
        }
        if phone_number is not None:
            data["phone_number"] = phone_number
        if commission_split is not None:
            data["commission_split"] = commission_split
        return Agent.objects.create(**data)


class UpdateAgentService(BaseService):
    """Patch mutable agent fields."""

    required_action = AGENT_UPDATE

    editable_fields = {"first_name", "last_name", "email", "phone_number", "commission_split"}

    def run(self, *, agent: Agent, **changes: Any) -> Agent:
        if not changes:
            return agent

        invalid = set(changes) - self.editable_fields
        if invalid:
            raise ValidationError({"fields": f"Unsupported agent fields: {sorted(invalid)}"})

        for field, value in changes.items():
            setattr(agent, field, value)

        agent.full_clean()
        update_fields = list(changes.keys()) + ["updated_at"]
        agent.save(update_fields=update_fields)
        return agent


__all__ = ["CreateAgentService", "UpdateAgentService"]
