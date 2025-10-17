"""Opportunity service utilities and concrete services."""

from .base import BaseService, service_atomic  # noqa: F401
from .opportunities import (  # noqa: F401
    CreateOpportunityService,
    OpportunityCloseService,
    OpportunityPublishService,
    OpportunityValidateService,
)
from .acquisition import (  # noqa: F401
    AcquisitionAttemptAppraiseService,
    AcquisitionAttemptCaptureService,
    AcquisitionAttemptRejectService,
)
from .validation import (  # noqa: F401
    ValidationAcceptService,
    ValidationPresentService,
    ValidationRejectService,
)
from .marketing import (  # noqa: F401
    MarketingPackageActivateService,
    MarketingPackageReleaseService,
    MarketingPackageReserveService,
)
from .operations import (  # noqa: F401
    OperationCloseService,
    OperationLoseService,
    OperationReinforceService,
)

__all__ = [
    "BaseService",
    "service_atomic",
    "CreateOpportunityService",
    "OpportunityValidateService",
    "OpportunityPublishService",
    "OpportunityCloseService",
    "AcquisitionAttemptAppraiseService",
    "AcquisitionAttemptCaptureService",
    "AcquisitionAttemptRejectService",
    "ValidationPresentService",
    "ValidationRejectService",
    "ValidationAcceptService",
    "MarketingPackageActivateService",
    "MarketingPackageReserveService",
    "MarketingPackageReleaseService",
    "OperationReinforceService",
    "OperationCloseService",
    "OperationLoseService",
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
