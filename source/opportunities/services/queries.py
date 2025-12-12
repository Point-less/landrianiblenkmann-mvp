"""Read-only query services for opportunities domain."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from utils.authorization import (
    OPERATION_VIEW,
    OPERATION_VIEW_ALL,
    PROVIDER_OPPORTUNITY_VIEW,
    PROVIDER_OPPORTUNITY_VIEW_ALL,
    SEEKER_OPPORTUNITY_VIEW,
    SEEKER_OPPORTUNITY_VIEW_ALL,
    check,
    filter_queryset,
)
from utils.services import BaseService
from opportunities.models import MarketingPackage, Operation, OperationAgreement, ProviderOpportunity, SeekerOpportunity, Validation


class AvailableProviderOpportunitiesForOperationsQuery(BaseService):
    """Providers that can be paired to a new operation.

    Actor is accepted for future authorization/filtering hooks.
    """

    def run(self, *, actor=None, exclude_agent: bool = False):  # actor kept for parity with other services
        queryset = ProviderOpportunity.objects.filter(
            state=ProviderOpportunity.State.MARKETING,
        ).order_by("-created_at")
        queryset = filter_queryset(
            actor,
            PROVIDER_OPPORTUNITY_VIEW,
            queryset,
            owner_field="source_intention__agent",
            view_all_action=PROVIDER_OPPORTUNITY_VIEW_ALL,
        )
        if exclude_agent:
            from utils.authorization import get_role_profile

            actor_agent = get_role_profile(actor, "agent") if actor else None
            if actor_agent:
                queryset = queryset.exclude(source_intention__agent=actor_agent)
        return queryset


class AvailableSeekerOpportunitiesForOperationsQuery(BaseService):
    """Seekers that can be paired to a new operation."""

    def run(self, *, actor=None, only_actor: bool = False):
        queryset = SeekerOpportunity.objects.filter(
            state=SeekerOpportunity.State.MATCHING
        ).order_by("-created_at")
        queryset = filter_queryset(
            actor,
            SEEKER_OPPORTUNITY_VIEW,
            queryset,
            owner_field="source_intention__agent",
            view_all_action=SEEKER_OPPORTUNITY_VIEW_ALL,
        )
        if only_actor:
            from utils.authorization import get_role_profile

            actor_agent = get_role_profile(actor, "agent") if actor else None
            if actor_agent:
                queryset = queryset.filter(source_intention__agent=actor_agent)
        return queryset


class DashboardProviderOpportunitiesQuery(BaseService):
    def run(self, *, actor=None):
        queryset = ProviderOpportunity.objects.select_related('source_intention__property', 'source_intention__owner').prefetch_related('state_transitions', 'validations').order_by('-created_at')
        return filter_queryset(
            actor,
            PROVIDER_OPPORTUNITY_VIEW,
            queryset,
            owner_field='source_intention__agent',
            view_all_action=PROVIDER_OPPORTUNITY_VIEW_ALL,
        )


class DashboardSeekerOpportunitiesQuery(BaseService):
    def run(self, *, actor=None):
        queryset = SeekerOpportunity.objects.select_related('source_intention__contact', 'source_intention__agent').prefetch_related('state_transitions').order_by('-created_at')
        return filter_queryset(
            actor,
            SEEKER_OPPORTUNITY_VIEW,
            queryset,
            owner_field='source_intention__agent',
            view_all_action=SEEKER_OPPORTUNITY_VIEW_ALL,
        )


class DashboardOperationsQuery(BaseService):
    def run(self, *, actor=None):
        check(actor, OPERATION_VIEW)
        queryset = Operation.objects.select_related(
            'agreement__provider_opportunity__source_intention__owner',
            'agreement__seeker_opportunity__source_intention__contact',
        ).prefetch_related('state_transitions').order_by('-created_at')

        try:
            check(actor, OPERATION_VIEW_ALL)
            return queryset
        except PermissionDenied:
            pass

        from utils.authorization import get_role_profile  # local import to avoid cycles

        owner = get_role_profile(actor, "agent") if actor else None
        if owner is None:
            return queryset.none()

        return queryset.filter(
            Q(agreement__provider_opportunity__source_intention__agent=owner)
            | Q(agreement__seeker_opportunity__source_intention__agent=owner)
        )


class DashboardProviderValidationsQuery(BaseService):
    def run(self, *, actor=None):
        queryset = Validation.objects.select_related('opportunity__source_intention__property').prefetch_related('documents', 'state_transitions').order_by('-created_at')
        return filter_queryset(
            actor,
            PROVIDER_OPPORTUNITY_VIEW,
            queryset,
            owner_field='opportunity__source_intention__agent',
            view_all_action=PROVIDER_OPPORTUNITY_VIEW_ALL,
        )


class DashboardMarketingPackagesQuery(BaseService):
    def run(self, *, actor=None):
        queryset = MarketingPackage.objects.select_related(
            'opportunity__source_intention__property',
            'opportunity__source_intention__owner'
        ).prefetch_related('state_transitions').filter(opportunity__state=ProviderOpportunity.State.MARKETING).order_by('-updated_at')
        return filter_queryset(
            actor,
            PROVIDER_OPPORTUNITY_VIEW,
            queryset,
            owner_field='opportunity__source_intention__agent',
            view_all_action=PROVIDER_OPPORTUNITY_VIEW_ALL,
        )


class DashboardMarketingOpportunitiesWithoutPackagesQuery(BaseService):
    def run(self, *, actor=None):
        queryset = ProviderOpportunity.objects.filter(
            state=ProviderOpportunity.State.MARKETING,
            marketing_packages__isnull=True,
        ).select_related('source_intention__property').prefetch_related('state_transitions')
        return filter_queryset(
            actor,
            PROVIDER_OPPORTUNITY_VIEW,
            queryset,
            owner_field='source_intention__agent',
            view_all_action=PROVIDER_OPPORTUNITY_VIEW_ALL,
        )


class ProviderOpportunitiesQuery(BaseService):
    """Generic provider opportunities listing (GraphQL / API)."""

    def run(self, *, actor=None):
        queryset = ProviderOpportunity.objects.select_related(
            'source_intention__property', 'source_intention__owner'
        ).order_by('-created_at')
        return filter_queryset(
            actor,
            PROVIDER_OPPORTUNITY_VIEW,
            queryset,
            owner_field='source_intention__agent',
            view_all_action=PROVIDER_OPPORTUNITY_VIEW_ALL,
        )


class SeekerOpportunitiesQuery(BaseService):
    """Generic seeker opportunities listing (GraphQL / API)."""

    def run(self, *, actor=None):
        queryset = SeekerOpportunity.objects.select_related(
            'source_intention__contact', 'source_intention__agent'
        ).order_by('-created_at')
        return filter_queryset(
            actor,
            SEEKER_OPPORTUNITY_VIEW,
            queryset,
            owner_field='source_intention__agent',
            view_all_action=SEEKER_OPPORTUNITY_VIEW_ALL,
        )


class OperationAgreementsQuery(BaseService):
    """Generic operation agreements listing (GraphQL / API)."""

    def run(self, *, actor=None):
        check(actor, OPERATION_VIEW)
        queryset = OperationAgreement.objects.select_related(
            'provider_opportunity', 'seeker_opportunity'
        ).order_by('-created_at')

        try:
            check(actor, OPERATION_VIEW_ALL)
            return queryset
        except PermissionDenied:
            pass

        from utils.authorization import get_role_profile

        owner = get_role_profile(actor, "agent") if actor else None
        if owner is None:
            return queryset.none()

        return queryset.filter(
            Q(provider_opportunity__source_intention__agent=owner)
            | Q(seeker_opportunity__source_intention__agent=owner)
        )


class ProviderOpportunityByTokkobrokerPropertyQuery(BaseService):
    """Check for existing opportunities linked to a Tokkobroker property."""

    def run(self, *, tokkobroker_property):
        return ProviderOpportunity.objects.filter(tokkobroker_property=tokkobroker_property)


class MarketingPackageByIdQuery(BaseService):
    """Fetch marketing package with currency for syncing/integrations."""

    def run(self, *, pk: int):
        return MarketingPackage.objects.select_related("currency").get(pk=pk)


class ActiveOperationsBetweenOpportunitiesQuery(BaseService):
    """Active operations between a provider and seeker opportunity pair."""

    def run(self, *, provider_opportunity: ProviderOpportunity, seeker_opportunity: SeekerOpportunity):
        active_states = (Operation.State.OFFERED, Operation.State.REINFORCED)
        return Operation.objects.filter(
            agreement__provider_opportunity=provider_opportunity,
            agreement__seeker_opportunity=seeker_opportunity,
            state__in=active_states,
        )


class SeekerActiveOperationsQuery(BaseService):
    """Active operations for a seeker opportunity."""

    def run(self, *, seeker_opportunity: SeekerOpportunity):
        active_states = (Operation.State.OFFERED, Operation.State.REINFORCED)
        return Operation.objects.filter(
            agreement__seeker_opportunity=seeker_opportunity,
            state__in=active_states,
        )


__all__ = [
    "AvailableProviderOpportunitiesForOperationsQuery",
    "AvailableSeekerOpportunitiesForOperationsQuery",
    "DashboardProviderOpportunitiesQuery",
    "DashboardSeekerOpportunitiesQuery",
    "DashboardOperationsQuery",
    "DashboardProviderValidationsQuery",
    "DashboardMarketingPackagesQuery",
    "DashboardMarketingOpportunitiesWithoutPackagesQuery",
    "ProviderOpportunitiesQuery",
    "SeekerOpportunitiesQuery",
    "ProviderOpportunityByTokkobrokerPropertyQuery",
    "MarketingPackageByIdQuery",
    "ActiveOperationsBetweenOpportunitiesQuery",
    "SeekerActiveOperationsQuery",
    "OperationAgreementsQuery",
]
