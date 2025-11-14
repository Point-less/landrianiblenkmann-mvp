"""Service objects for agent management."""

from typing import Any

from django.core.exceptions import ValidationError

from core.models import Agent
from utils.services import BaseService


class CreateAgentService(BaseService):
    """Register a new sales agent."""

    def run(
        self,
        *,
        first_name: str,
        last_name: str = "",
        email: str | None = None,
        phone_number: str | None = None,
    ) -> Agent:
        return Agent.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email or "",
            phone_number=phone_number or "",
        )


class UpdateAgentService(BaseService):
    """Patch mutable agent fields."""

    editable_fields = {"first_name", "last_name", "email", "phone_number"}

    def run(self, *, agent: Agent, **changes: Any) -> Agent:
        if not changes:
            return agent

        invalid = set(changes) - self.editable_fields
        if invalid:
            raise ValidationError({"fields": f"Unsupported agent fields: {sorted(invalid)}"})

        for field, value in changes.items():
            normalized = value if value is not None else ""
            setattr(agent, field, normalized)

        agent.full_clean()
        update_fields = list(changes.keys()) + ["updated_at"]
        agent.save(update_fields=update_fields)
        return agent


__all__ = ["CreateAgentService", "UpdateAgentService"]
