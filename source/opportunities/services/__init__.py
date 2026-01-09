"""Opportunity service utilities and concrete services."""

from utils.services import BaseService, service_atomic  # noqa: F401
from .opportunities import (  # noqa: F401
    CreateOpportunityService,
    CreateSeekerOpportunityService,
    OpportunityCloseService,
    OpportunityPublishService,
)
from .validation import (  # noqa: F401
    ValidationAcceptService,
    ValidationEnsureService,
    ValidationPresentService,
    ValidationRejectService,
)
from .marketing import (  # noqa: F401
    MarketingPackageActivateService,
    MarketingPackageReleaseService,
    MarketingPackageCreateService,
    MarketingPackageUpdateService,
    MarketingPackagePauseService,
)
from .operations import (  # noqa: F401
    CreateOperationService,
    OperationCloseService,
    OperationLoseService,
    OperationReinforceService,
)
from .agreements import (  # noqa: F401
    CreateOperationAgreementService,
    AgreeOperationAgreementService,
    SignOperationAgreementService,
    RevokeOperationAgreementService,
    CancelOperationAgreementService,
)
from .queries import (  # noqa: F401
    AvailableProviderOpportunitiesForOperationsQuery,
    AvailableSeekerOpportunitiesForOperationsQuery,
    DashboardProviderOpportunitiesQuery,
    DashboardSeekerOpportunitiesQuery,
    DashboardOperationsQuery,
    DashboardProviderValidationsQuery,
    DashboardMarketingPackagesQuery,
    DashboardMarketingOpportunitiesWithoutPackagesQuery,
    MarketingPackagesWithRevisionsForOpportunityQuery,
    ProviderOpportunitiesQuery,
    SeekerOpportunitiesQuery,
    ProviderOpportunityByTokkobrokerPropertyQuery,
    MarketingPackageByIdQuery,
    OperationAgreementsQuery,
    OperationAgreementChoicesQuery,
)
from .validation_docs import (  # noqa: F401
    CreateValidationDocumentService,
    CreateAdditionalValidationDocumentService,
    ReviewValidationDocumentService,
    AllowedValidationDocumentTypesQuery,
)

__all__ = [
    "BaseService",
    "service_atomic",
    "CreateOpportunityService",
    "OpportunityPublishService",
    "OpportunityCloseService",
    "CreateSeekerOpportunityService",
    "ValidationPresentService",
    "ValidationRejectService",
    "ValidationEnsureService",
    "ValidationAcceptService",
    "MarketingPackageActivateService",
    "MarketingPackageReleaseService",
    "MarketingPackageCreateService",
    "MarketingPackageUpdateService",
    "MarketingPackagePauseService",
    "CreateOperationService",
    "OperationReinforceService",
    "OperationCloseService",
    "OperationLoseService",
    "CreateOperationAgreementService",
    "AgreeOperationAgreementService",
    "SignOperationAgreementService",
    "RevokeOperationAgreementService",
    "CancelOperationAgreementService",
    "AvailableProviderOpportunitiesForOperationsQuery",
    "AvailableSeekerOpportunitiesForOperationsQuery",
    "DashboardProviderOpportunitiesQuery",
    "DashboardSeekerOpportunitiesQuery",
    "DashboardOperationsQuery",
    "DashboardProviderValidationsQuery",
    "DashboardMarketingPackagesQuery",
    "DashboardMarketingOpportunitiesWithoutPackagesQuery",
    "MarketingPackagesWithRevisionsForOpportunityQuery",
    "ProviderOpportunitiesQuery",
    "SeekerOpportunitiesQuery",
    "ProviderOpportunityByTokkobrokerPropertyQuery",
    "MarketingPackageByIdQuery",
    "OperationAgreementsQuery",
    "OperationAgreementChoicesQuery",
    "CreateValidationDocumentService",
    "CreateAdditionalValidationDocumentService",
    "ReviewValidationDocumentService",
    "AllowedValidationDocumentTypesQuery",
    "discover_services",
    "get_services",
    "iter_services",
    "resolve_service",
    "ServiceInvoker",
    "for_actor",
]

_SERVICE_ATTRS = {
    "discover_services",
    "get_services",
    "iter_services",
    "resolve_service",
    "ServiceInvoker",
    "for_actor",
}


def __getattr__(name):
    if name in _SERVICE_ATTRS:
        from utils import services as service_registry

        return getattr(service_registry, name)
    raise AttributeError(f"module 'opportunities.services' has no attribute {name!r}")
