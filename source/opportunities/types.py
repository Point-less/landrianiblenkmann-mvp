import strawberry
import strawberry_django
from strawberry import relay

from django_fsm import FSMField
from strawberry_django.fields import types as strawberry_types

strawberry_types.field_type_map.setdefault(FSMField, str)

from opportunities.models import (
    AcquisitionAttempt,
    Agent,
    Appraisal,
    Contact,
    ContactAgentRelationship,
    MarketingPackage,
    Operation,
    Opportunity,
    Property,
    Validation,
)
from core.models import Currency


@strawberry_django.type(Contact, fields="__all__")
class ContactType(relay.Node):
    pass


@strawberry_django.type(Agent, fields="__all__")
class AgentType(relay.Node):
    pass


@strawberry_django.type(ContactAgentRelationship, fields="__all__")
class ContactAgentRelationshipType(relay.Node):
    pass


@strawberry_django.type(Currency, fields="__all__")
class CurrencyType(relay.Node):
    pass


@strawberry_django.type(Property, fields="__all__")
class PropertyType(relay.Node):
    pass


@strawberry_django.type(AcquisitionAttempt, fields="__all__")
class AcquisitionAttemptType(relay.Node):
    state: str = strawberry_django.field()


@strawberry_django.type(Appraisal, fields="__all__")
class AppraisalType(relay.Node):
    pass


@strawberry_django.type(Validation, fields="__all__")
class ValidationType(relay.Node):
    state: str = strawberry_django.field()


@strawberry_django.type(MarketingPackage, fields="__all__")
class MarketingPackageType(relay.Node):
    state: str = strawberry_django.field()


@strawberry_django.type(Operation, fields="__all__")
class OperationType(relay.Node):
    state: str = strawberry_django.field()


@strawberry_django.type(Opportunity, fields="__all__")
class OpportunityType(relay.Node):
    state: str = strawberry_django.field()


__all__ = [
    "ContactType",
    "AgentType",
    "ContactAgentRelationshipType",
    "CurrencyType",
    "PropertyType",
    "AcquisitionAttemptType",
    "AppraisalType",
    "ValidationType",
    "MarketingPackageType",
    "OperationType",
    "OpportunityType",
]
