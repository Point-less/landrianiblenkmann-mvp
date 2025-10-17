import strawberry
import strawberry_django
from strawberry import relay

from opportunities.filters import OpportunityFilter
from opportunities.types import OpportunityType


@strawberry.type
class OpportunitiesQuery:
    opportunities: relay.ListConnection[OpportunityType] = strawberry_django.connection(
        relay.ListConnection[OpportunityType],
        filters=OpportunityFilter,
    )


__all__ = ["OpportunitiesQuery", "OpportunityType"]
