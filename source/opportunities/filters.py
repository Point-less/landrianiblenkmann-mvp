import strawberry
import strawberry_django

from opportunities.models import ProviderOpportunity, SeekerOpportunity


@strawberry_django.filter(ProviderOpportunity)
class ProviderOpportunityFilter:
    id: strawberry.auto
    title: strawberry.auto
    state: strawberry.auto
    source_intention_id: strawberry.auto


@strawberry_django.filter(SeekerOpportunity)
class SeekerOpportunityFilter:
    id: strawberry.auto
    title: strawberry.auto
    state: strawberry.auto
    source_intention_id: strawberry.auto


__all__ = ["ProviderOpportunityFilter", "SeekerOpportunityFilter"]
