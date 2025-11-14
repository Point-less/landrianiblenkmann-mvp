"""Opportunity service utilities and concrete services."""

from utils.services import BaseService, service_atomic  # noqa: F401
from .opportunities import (  # noqa: F401
    CreateOpportunityService,
    CreateSeekerOpportunityService,
    OpportunityCloseService,
    OpportunityPublishService,
    OpportunityValidateService,
)
from .validation import (  # noqa: F401
    ValidationAcceptService,
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
from .validation_docs import (  # noqa: F401
    CreateValidationDocumentService,
    ReviewValidationDocumentService,
)

__all__ = [
    "BaseService",
    "service_atomic",
    "CreateOpportunityService",
    "OpportunityValidateService",
    "OpportunityPublishService",
    "OpportunityCloseService",
    "CreateSeekerOpportunityService",
    "ValidationPresentService",
    "ValidationRejectService",
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
    "CreateValidationDocumentService",
    "ReviewValidationDocumentService",
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
