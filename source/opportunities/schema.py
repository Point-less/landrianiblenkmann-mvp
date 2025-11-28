from __future__ import annotations

from typing import Iterable

import strawberry
import strawberry_django
from strawberry import relay

from opportunities.filters import ProviderOpportunityFilter, SeekerOpportunityFilter
from opportunities.types import ProviderOpportunityType, SeekerOpportunityType
from opportunities.services import ProviderOpportunitiesQuery, SeekerOpportunitiesQuery


def _resolve_provider_opportunities(
    root,
    info,
    filters: ProviderOpportunityFilter | None,
) -> Iterable[ProviderOpportunityType]:
    request = info.context.request
    return ProviderOpportunitiesQuery.call(actor=request.user)


def _resolve_seeker_opportunities(
    root,
    info,
    filters: SeekerOpportunityFilter | None,
) -> Iterable[SeekerOpportunityType]:
    request = info.context.request
    return SeekerOpportunitiesQuery.call(actor=request.user)


@strawberry.type
class OpportunitiesQuery:
    provider_opportunities: relay.ListConnection[ProviderOpportunityType] = strawberry_django.connection(
        relay.ListConnection[ProviderOpportunityType],
        filters=ProviderOpportunityFilter,
        resolver=_resolve_provider_opportunities,
    )
    seeker_opportunities: relay.ListConnection[SeekerOpportunityType] = strawberry_django.connection(
        relay.ListConnection[SeekerOpportunityType],
        filters=SeekerOpportunityFilter,
        resolver=_resolve_seeker_opportunities,
    )


__all__ = ["OpportunitiesQuery", "ProviderOpportunityType", "SeekerOpportunityType"]
