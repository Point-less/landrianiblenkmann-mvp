import strawberry
import strawberry_django

from opportunities.models import Opportunity


@strawberry_django.filter(Opportunity)
class OpportunityFilter:
    id: strawberry.auto
    title: strawberry.auto
    state: strawberry.auto
    agent_id: strawberry.auto
    property_id: strawberry.auto
    owner_id: strawberry.auto


__all__ = ["OpportunityFilter"]
