from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import ObjectGrant, Permission, Role, RoleMembership, RolePermission

User = get_user_model()


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    list_filter = ('is_staff', 'is_superuser', 'is_active')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "profile_content_type")
    search_fields = ("slug", "name")


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "description")
    search_fields = ("code",)


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "allowed")
    list_filter = ("role", "allowed")
    search_fields = ("permission__code", "role__slug")


@admin.register(RoleMembership)
class RoleMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "profile")
    list_filter = ("role",)
    search_fields = ("user__username", "role__slug")


@admin.register(ObjectGrant)
class ObjectGrantAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "permission", "content_type", "object_id", "allowed")
    list_filter = ("permission", "allowed")
    search_fields = ("permission__code",)
