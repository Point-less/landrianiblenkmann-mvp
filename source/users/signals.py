from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from users.models import RolePermission, RoleMembership, ObjectGrant
from utils.authorization import invalidate_user_cache


def _invalidate_for_role(role_id):
    from users.models import RoleMembership  # local import to avoid import loops

    user_ids = (
        RoleMembership.objects.filter(role_id=role_id)  # service-guard: allow (cache invalidation)
        .values_list("user_id", flat=True)
        .distinct()
    )
    for uid in user_ids:
        invalidate_user_cache(uid)


@receiver([post_save, post_delete], sender=RoleMembership)
def clear_cache_on_membership_change(sender, instance, **kwargs):
    invalidate_user_cache(instance.user_id)


@receiver([post_save, post_delete], sender=RolePermission)
def clear_cache_on_role_permission_change(sender, instance, **kwargs):
    _invalidate_for_role(instance.role_id)


@receiver([post_save, post_delete], sender=ObjectGrant)
def clear_cache_on_object_grant_change(sender, instance, **kwargs):
    if instance.user_id:
        invalidate_user_cache(instance.user_id)
    if instance.role_id:
        _invalidate_for_role(instance.role_id)
