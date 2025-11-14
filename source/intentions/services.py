from typing import Any, Mapping

from django.core.exceptions import ValidationError

from opportunities.services import CreateOpportunityService
from utils.services import BaseService

from .models import SaleProviderIntention


class PromoteSaleProviderIntentionService(BaseService):
    """Promote a provider intention into a fully managed opportunity."""

    def run(
        self,
        *,
        intention: SaleProviderIntention,
        opportunity_title: str | None = None,
        opportunity_notes: str | None = None,
        marketing_package_data: Mapping[str, Any] | None = None,
    ):
        if not intention.is_promotable():
            raise ValidationError("Intention must have approved documents and not be converted yet.")

        opportunity_payload = {
            "title": opportunity_title or f"Listing for {intention.property.name}",
            "property": intention.property,
            "agent": intention.agent,
            "owner": intention.owner,
            "notes": opportunity_notes or intention.documentation_notes,
        }

        opportunity = CreateOpportunityService.call(
            opportunity_data=opportunity_payload,
            marketing_package_data=marketing_package_data,
        )

        intention.mark_converted(opportunity=opportunity)
        intention.save(
            update_fields=[
                "state",
                "converted_opportunity",
                "converted_at",
                "updated_at",
            ]
        )
        return opportunity


__all__ = ["PromoteSaleProviderIntentionService"]
