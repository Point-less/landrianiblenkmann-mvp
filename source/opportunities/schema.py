from __future__ import annotations

from typing import Any, Iterable

import strawberry
import strawberry_django
from strawberry import relay
from strawberry_django import filters as dj_filters
from django.db.models import QuerySet

from opportunities.filters import OperationAgreementFilter, ProviderOpportunityFilter, SeekerOpportunityFilter
from opportunities.types import OperationAgreementType, ProviderOpportunityType, SeekerOpportunityType
from utils.services import S


def _apply_filters(queryset: QuerySet, filters: Any, info: Any) -> QuerySet:
    return dj_filters.apply(filters, queryset, info=info) if filters else queryset


def _resolve_provider_opportunities(
    root,
    info,
    filters: ProviderOpportunityFilter | None,
) -> Iterable[ProviderOpportunityType]:
    request = info.context.request
    queryset = S.opportunities.ProviderOpportunitiesQuery(actor=request.user)
    return _apply_filters(queryset, filters, info)


def _resolve_operation_agreements(
    root,
    info,
    filters: OperationAgreementFilter | None,
) -> Iterable[OperationAgreementType]:
    request = info.context.request
    queryset = S.opportunities.OperationAgreementsQuery(actor=request.user)
    return _apply_filters(queryset, filters, info)


def _resolve_seeker_opportunities(
    root,
    info,
    filters: SeekerOpportunityFilter | None,
) -> Iterable[SeekerOpportunityType]:
    request = info.context.request
    queryset = S.opportunities.SeekerOpportunitiesQuery(actor=request.user)
    return _apply_filters(queryset, filters, info)


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
    operation_agreements: relay.ListConnection[OperationAgreementType] = strawberry_django.connection(
        relay.ListConnection[OperationAgreementType],
        filters=OperationAgreementFilter,
        resolver=_resolve_operation_agreements,
    )


__all__ = ["OpportunitiesQuery", "ProviderOpportunityType", "SeekerOpportunityType", "OperationAgreementType"]
