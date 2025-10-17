from typing import Any, Mapping

from core.models import MarketingPackage, Opportunity
from core.services.base import BaseService


class CreateOpportunityService(BaseService):
    """Create an opportunity with an optional initial marketing package."""

    def run(
        self,
        *,
        opportunity_data: Mapping[str, Any],
        marketing_package_data: Mapping[str, Any] | None = None,
    ) -> Opportunity:
        marketing_payload = dict(marketing_package_data or {})
        opportunity = Opportunity.objects.create(**opportunity_data)

        marketing_payload.setdefault("headline", opportunity.title)

        MarketingPackage.objects.create(
            opportunity=opportunity,
            **marketing_payload,
        )

        return opportunity
