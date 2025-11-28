"""Read-only query services for opportunities domain."""

from __future__ import annotations

from utils.services import BaseService
from opportunities.models import ProviderOpportunity, SeekerOpportunity


class AvailableProviderOpportunitiesForOperationsQuery(BaseService):
    """Providers that can be paired to a new operation.

    Actor is accepted for future authorization/filtering hooks.
    """

    def run(self, *, actor=None):  # actor kept for parity with other services
        queryset = ProviderOpportunity.objects.filter(
            state=ProviderOpportunity.State.MARKETING
        ).order_by("-created_at")
        return queryset


class AvailableSeekerOpportunitiesForOperationsQuery(BaseService):
    """Seekers that can be paired to a new operation."""

    def run(self, *, actor=None):
        queryset = SeekerOpportunity.objects.filter(
            state=SeekerOpportunity.State.MATCHING
        ).order_by("-created_at")
        return queryset


__all__ = [
    "AvailableProviderOpportunitiesForOperationsQuery",
    "AvailableSeekerOpportunitiesForOperationsQuery",
]
