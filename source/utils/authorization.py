"""Centralized authorization helpers (single source of truth).

Usage surfaces (services, views, GraphQL, templates) should only import
`Action`, `check`, `filter_queryset`, and `explain`. No other module should
encode role/permission logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db.models import Model, Q, QuerySet

from users.models import ObjectGrant, Permission, RoleMembership, RolePermission


# ---- Canonical actions ----------------------------------------------------


@dataclass(frozen=True)
class Action:
    code: str


# Core entity actions
AGENT_VIEW = Action("agent.view")
AGENT_VIEW_ALL = Action("agent.view_all")

CONTACT_VIEW = Action("contact.view")
CONTACT_VIEW_ALL = Action("contact.view_all")

PROPERTY_VIEW = Action("property.view")
PROPERTY_VIEW_ALL = Action("property.view_all")

AGENT_CREATE = Action("agent.create")
AGENT_UPDATE = Action("agent.update")
CONTACT_CREATE = Action("contact.create")
CONTACT_UPDATE = Action("contact.update")
PROPERTY_CREATE = Action("property.create")
PROPERTY_UPDATE = Action("property.update")

PROVIDER_INTENTION_VIEW = Action("provider_intention.view")
PROVIDER_INTENTION_VIEW_ALL = Action("provider_intention.view_all")
PROVIDER_INTENTION_CREATE = Action("provider_intention.create")
PROVIDER_INTENTION_VALUATE = Action("provider_intention.deliver_valuation")
PROVIDER_INTENTION_WITHDRAW = Action("provider_intention.withdraw")
PROVIDER_INTENTION_PROMOTE = Action("provider_intention.promote")

SEEKER_INTENTION_VIEW = Action("seeker_intention.view")
SEEKER_INTENTION_VIEW_ALL = Action("seeker_intention.view_all")
SEEKER_INTENTION_CREATE = Action("seeker_intention.create")
SEEKER_INTENTION_ABANDON = Action("seeker_intention.abandon")

PROVIDER_OPPORTUNITY_VIEW = Action("provider_opportunity.view")
PROVIDER_OPPORTUNITY_VIEW_ALL = Action("provider_opportunity.view_all")
PROVIDER_OPPORTUNITY_CREATE = Action("provider_opportunity.create")
PROVIDER_OPPORTUNITY_PUBLISH = Action("provider_opportunity.publish")
PROVIDER_OPPORTUNITY_CLOSE = Action("provider_opportunity.close")

SEEKER_OPPORTUNITY_VIEW = Action("seeker_opportunity.view")
SEEKER_OPPORTUNITY_VIEW_ALL = Action("seeker_opportunity.view_all")
SEEKER_OPPORTUNITY_CREATE = Action("seeker_opportunity.create")

OPERATION_VIEW = Action("operation.view")
OPERATION_VIEW_ALL = Action("operation.view_all")
OPERATION_CREATE = Action("operation.create")
OPERATION_REINFORCE = Action("operation.reinforce")
OPERATION_LOSE = Action("operation.lose")
OPERATION_CLOSE = Action("operation.close")

AGREEMENT_CREATE = Action("operation_agreement.create")
AGREEMENT_AGREE = Action("operation_agreement.agree")
AGREEMENT_SIGN = Action("operation_agreement.sign")
AGREEMENT_REVOKE = Action("operation_agreement.revoke")
AGREEMENT_CANCEL = Action("operation_agreement.cancel")

REPORT_VIEW = Action("report.view")

USER_VIEW = Action("user.view")
USER_VIEW_ALL = Action("user.view_all")

INTEGRATION_VIEW = Action("integration.view")
INTEGRATION_MANAGE = Action("integration.manage")


# ---- Internal helpers -----------------------------------------------------


def _membership_roles(user) -> Iterable[int]:
    return (
        RoleMembership.objects.filter(user=user)
        .values_list("role_id", flat=True)
        .distinct()
    )


def _perms_for_user(user):
    """Return ({global set}, {(ct, obj): set(codes)}).

    Cached per-user for 5 minutes to keep checks fast.
    """

    cache_key = f"auth_perms:{getattr(user, 'pk', None)}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    role_ids = list(_membership_roles(user))
    global_codes = set(
        RolePermission.objects.filter(role_id__in=role_ids, allowed=True)
        .select_related("permission")
        .values_list("permission__code", flat=True)
    )

    grants_qs = ObjectGrant.objects.filter(allowed=True).select_related("permission")
    if user.is_authenticated:
        grants_qs = grants_qs.filter(Q(user=user) | Q(role_id__in=role_ids))
    else:
        grants_qs = grants_qs.none()

    object_codes = {}
    for ct_id, obj_id, code in grants_qs.values_list("content_type_id", "object_id", "permission__code"):
        object_codes.setdefault((ct_id, obj_id), set()).add(code)

    data = {"global": global_codes, "object": object_codes}
    cache.set(cache_key, data, timeout=300)
    return data


def invalidate_user_cache(user_id: int | None):
    if user_id is None:
        return
    cache.delete(f"auth_perms:{user_id}")


def get_role_profile(user, role_slug: str) -> Optional[Model]:
    """Return the profile object linked to `role_slug`, or None."""

    membership = (
        RoleMembership.objects.select_related("role", "profile_content_type")
        .filter(user=user, role__slug=role_slug)
        .first()
    )
    if not membership:
        return None
    return membership.profile


# ---- Public API -----------------------------------------------------------


def check(user, action: Action, obj: Optional[Model] = None) -> bool:
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication required")

    if getattr(user, "is_superuser", False):
        return True

    perms = _perms_for_user(user)

    if action.code in perms["global"]:
        return True

    if obj is not None:
        ct_id = ContentType.objects.get_for_model(obj).id
        if action.code in perms["object"].get((ct_id, obj.pk), set()):
            return True

    raise PermissionDenied(f"Missing permission: {action.code}")


def filter_queryset(
    user,
    action: Action,
    qs: QuerySet,
    *,
    owner_field: str = "agent",
    view_all_action: Optional[Action] = None,
):
    """Enforce row-level visibility.

    - If user has view_all_action (or inferred <model>.view_all) -> return qs
    - Else, if user has owner profile for `agent` role -> filter by owner_field
    - Else -> empty qs
    """

    if not getattr(user, "is_authenticated", False):
        return qs.none()

    if getattr(user, "is_superuser", False):
        return qs

    perms = _perms_for_user(user)
    if view_all_action is None:
        inferred = f"{qs.model._meta.model_name}.view_all"
        view_all_action = Action(inferred)

    if view_all_action.code in perms["global"]:
        return qs

    owner_obj = get_role_profile(user, "agent")
    if owner_obj is None:
        return qs.none()

    return qs.filter(**{owner_field: owner_obj})


def explain(user, action: Action, obj: Optional[Model] = None) -> str:
    try:
        check(user, action, obj)
        return f"Allowed: {action.code}"
    except PermissionDenied as exc:  # pragma: no cover - used in admin/debug
        return str(exc)


__all__ = [
    "Action",
    "check",
    "filter_queryset",
    "explain",
    # constants
    "AGENT_VIEW",
    "AGENT_VIEW_ALL",
    "AGENT_CREATE",
    "AGENT_UPDATE",
    "CONTACT_VIEW",
    "CONTACT_VIEW_ALL",
    "CONTACT_CREATE",
    "CONTACT_UPDATE",
    "PROPERTY_VIEW",
    "PROPERTY_VIEW_ALL",
    "PROPERTY_CREATE",
    "PROPERTY_UPDATE",
    "PROVIDER_INTENTION_VIEW",
    "PROVIDER_INTENTION_VIEW_ALL",
    "PROVIDER_INTENTION_CREATE",
    "PROVIDER_INTENTION_VALUATE",
    "PROVIDER_INTENTION_WITHDRAW",
    "PROVIDER_INTENTION_PROMOTE",
    "SEEKER_INTENTION_VIEW",
    "SEEKER_INTENTION_VIEW_ALL",
    "SEEKER_INTENTION_CREATE",
    "SEEKER_INTENTION_ABANDON",
    "PROVIDER_OPPORTUNITY_VIEW",
    "PROVIDER_OPPORTUNITY_VIEW_ALL",
    "PROVIDER_OPPORTUNITY_CREATE",
    "PROVIDER_OPPORTUNITY_PUBLISH",
    "PROVIDER_OPPORTUNITY_CLOSE",
    "SEEKER_OPPORTUNITY_VIEW",
    "SEEKER_OPPORTUNITY_VIEW_ALL",
    "SEEKER_OPPORTUNITY_CREATE",
    "OPERATION_VIEW",
    "OPERATION_VIEW_ALL",
    "OPERATION_CREATE",
    "OPERATION_REINFORCE",
    "OPERATION_LOSE",
    "OPERATION_CLOSE",
    "AGREEMENT_CREATE",
    "AGREEMENT_AGREE",
    "AGREEMENT_SIGN",
    "AGREEMENT_REVOKE",
    "AGREEMENT_CANCEL",
    "REPORT_VIEW",
    "USER_VIEW",
    "USER_VIEW_ALL",
    "INTEGRATION_VIEW",
    "INTEGRATION_MANAGE",
    "get_role_profile",
]
