"""Read-only query services for opportunities domain."""

from __future__ import annotations

from utils.services import BaseService
from opportunities.models import MarketingPackage, Operation, ProviderOpportunity, SeekerOpportunity, Validation


class AvailableProviderOpportunitiesForOperationsQuery(BaseService):
    """Providers that can be paired to a new operation.

    Actor is accepted for future authorization/filtering hooks.
    """

    def run(self, *, actor=None):  # actor kept for parity with other services
        queryset = ProviderOpportunity.objects.filter(
            state=ProviderOpportunity.State.MARKETING,
        ).order_by("-created_at")
        return queryset


class AvailableSeekerOpportunitiesForOperationsQuery(BaseService):
    """Seekers that can be paired to a new operation."""

    def run(self, *, actor=None):
        queryset = SeekerOpportunity.objects.filter(
            state=SeekerOpportunity.State.MATCHING
        ).order_by("-created_at")
        return queryset


class DashboardProviderOpportunitiesQuery(BaseService):
    def run(self, *, actor=None):
        return (
            ProviderOpportunity.objects.select_related('source_intention__property', 'source_intention__owner')
            .prefetch_related('state_transitions', 'validations')
            .order_by('-created_at')
        )


class DashboardSeekerOpportunitiesQuery(BaseService):
    def run(self, *, actor=None):
        return (
            SeekerOpportunity.objects.select_related('source_intention__contact', 'source_intention__agent')
            .prefetch_related('state_transitions')
            .order_by('-created_at')
        )


class DashboardOperationsQuery(BaseService):
    def run(self, *, actor=None):
        return (
            Operation.objects.select_related(
                'provider_opportunity__source_intention__owner',
                'seeker_opportunity__source_intention__contact',
            )
            .prefetch_related('state_transitions')
            .order_by('-created_at')
        )


class DashboardProviderValidationsQuery(BaseService):
    def run(self, *, actor=None):
        return (
            Validation.objects.select_related('opportunity__source_intention__property')
            .prefetch_related('documents', 'state_transitions')
            .order_by('-created_at')
        )


class DashboardMarketingPackagesQuery(BaseService):
    def run(self, *, actor=None):
        return (
            MarketingPackage.objects.select_related(
                'opportunity__source_intention__property',
                'opportunity__source_intention__owner'
            )
            .prefetch_related('state_transitions')
            .filter(opportunity__state=ProviderOpportunity.State.MARKETING)
            .order_by('-updated_at')
        )


class DashboardMarketingOpportunitiesWithoutPackagesQuery(BaseService):
    def run(self, *, actor=None):
        return (
            ProviderOpportunity.objects.filter(
                state=ProviderOpportunity.State.MARKETING,
                marketing_packages__isnull=True,
            )
            .select_related('source_intention__property')
            .prefetch_related('state_transitions')
        )


class ProviderOpportunitiesQuery(BaseService):
    """Generic provider opportunities listing (GraphQL / API)."""

    def run(self, *, actor=None):
        return ProviderOpportunity.objects.select_related(
            'source_intention__property', 'source_intention__owner'
        ).order_by('-created_at')


class SeekerOpportunitiesQuery(BaseService):
    """Generic seeker opportunities listing (GraphQL / API)."""

    def run(self, *, actor=None):
        return SeekerOpportunity.objects.select_related(
            'source_intention__contact', 'source_intention__agent'
        ).order_by('-created_at')


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
            provider_opportunity=provider_opportunity,
            seeker_opportunity=seeker_opportunity,
            state__in=active_states,
        )


class SeekerActiveOperationsQuery(BaseService):
    """Active operations for a seeker opportunity."""

    def run(self, *, seeker_opportunity: SeekerOpportunity):
        active_states = (Operation.State.OFFERED, Operation.State.REINFORCED)
        return Operation.objects.filter(
            seeker_opportunity=seeker_opportunity,
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
]
