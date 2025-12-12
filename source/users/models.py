from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from utils.mixins import TimeStampedMixin


class Role(TimeStampedMixin):
    """System role with an optional required profile model."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    profile_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text="If set, role memberships must point to this profile model.",
    )

    class Meta:
        ordering = ("slug",)

    def __str__(self) -> str:
        return self.name or self.slug


class Permission(TimeStampedMixin):
    """Action code that can be allowed/denied."""

    code = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.code


class RolePermission(TimeStampedMixin):
    """Matrix row for role -> permission (allow/deny)."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="role_permissions")
    allowed = models.BooleanField(default=True)

    class Meta:
        unique_together = ("role", "permission")
        ordering = ("role__slug", "permission__code")

    def __str__(self) -> str:
        return f"{self.role.slug}:{self.permission.code}={'allow' if self.allowed else 'deny'}"


class RoleMembership(TimeStampedMixin):
    """Assign a user to a role with an optional profile object (e.g., Agent)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="role_memberships")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="memberships")
    profile_content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE)
    profile_id = models.PositiveIntegerField(null=True, blank=True)
    profile = GenericForeignKey("profile_content_type", "profile_id")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="uniq_user_role_membership"),
            models.CheckConstraint(
                check=(
                    models.Q(profile_content_type__isnull=True, profile_id__isnull=True)
                    | models.Q(profile_content_type__isnull=False, profile_id__isnull=False)
                ),
                name="role_membership_profile_null_together",
            ),
        ]
        ordering = ("user_id", "role__slug")

    def clean(self):
        expected_ct = self.role.profile_content_type
        has_profile = self.profile_content_type is not None

        if expected_ct and not has_profile:
            raise ValidationError({"profile": f"Role '{self.role.slug}' requires a profile of type {expected_ct}."})
        if not expected_ct and has_profile:
            raise ValidationError({"profile": f"Role '{self.role.slug}' must not have a profile."})
        if expected_ct and has_profile and expected_ct != self.profile_content_type:
            raise ValidationError({"profile": f"Role '{self.role.slug}' requires profile type {expected_ct}, got {self.profile_content_type}."})

    def __str__(self) -> str:
        return f"{self.user} -> {self.role.slug}{' [' + str(self.profile) + ']' if self.profile else ''}"


class ObjectGrant(TimeStampedMixin):
    """Optional per-object override for users or roles."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="object_grants",
    )
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.CASCADE, related_name="object_grants")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="object_grants")
    allowed = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(models.Q(user__isnull=False) | models.Q(role__isnull=False)),
                name="object_grant_user_or_role",
            ),
        ]
        ordering = ("permission__code",)

    def __str__(self) -> str:
        target = self.user or self.role
        return f"{target} -> {self.permission.code} on {self.content_type_id}:{self.object_id}"


class User(AbstractUser):
    pass


__all__ = [
    "Role",
    "Permission",
    "RolePermission",
    "RoleMembership",
    "ObjectGrant",
    "User",
]
