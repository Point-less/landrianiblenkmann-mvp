import strawberry
import strawberry_django

from opportunities.models import ProviderOpportunity, SeekerOpportunity, OperationAgreement


@strawberry_django.filter(ProviderOpportunity)
class ProviderOpportunityFilter:
    id: strawberry.auto
    state: strawberry.auto
    source_intention_id: strawberry.auto


@strawberry_django.filter(SeekerOpportunity)
class SeekerOpportunityFilter:
    id: strawberry.auto
    state: strawberry.auto
    source_intention_id: strawberry.auto


@strawberry_django.filter(OperationAgreement)
class OperationAgreementFilter:
    id: strawberry.auto
    state: strawberry.auto
    provider_opportunity_id: strawberry.auto
    seeker_opportunity_id: strawberry.auto


__all__ = ["ProviderOpportunityFilter", "SeekerOpportunityFilter", "OperationAgreementFilter"]
