import strawberry
import strawberry_django
from strawberry import relay

from opportunities.filters import ProviderOpportunityFilter, SeekerOpportunityFilter
from opportunities.types import ProviderOpportunityType, SeekerOpportunityType


@strawberry.type
class OpportunitiesQuery:
    provider_opportunities: relay.ListConnection[ProviderOpportunityType] = strawberry_django.connection(
        relay.ListConnection[ProviderOpportunityType],
        filters=ProviderOpportunityFilter,
    )
    seeker_opportunities: relay.ListConnection[SeekerOpportunityType] = strawberry_django.connection(
        relay.ListConnection[SeekerOpportunityType],
        filters=SeekerOpportunityFilter,
    )


__all__ = ["OpportunitiesQuery", "ProviderOpportunityType", "SeekerOpportunityType"]
