from django.contrib import admin

from . import models


@admin.register(models.ProviderIntention)
class ProviderIntentionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "property",
        "owner",
        "agent",
        "state",
        "updated_at",
    )
    list_filter = ("state", "agent")
    search_fields = (
        "property__name",
        "owner__first_name",
        "owner__last_name",
    )
    raw_id_fields = ("owner", "agent", "property", "valuation")
    readonly_fields = ("created_at", "updated_at", "converted_at")


@admin.register(models.SeekerIntention)
class SeekerIntentionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "contact",
        "agent",
        "state",
        "budget_min",
        "budget_max",
        "updated_at",
    )
    list_filter = ("state", "agent")
    search_fields = (
        "contact__first_name",
        "contact__last_name",
    )
    raw_id_fields = ("contact", "agent")
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.Valuation)
class ValuationAdmin(admin.ModelAdmin):
    list_display = ("id", "provider_intention", "agent", "amount", "currency", "delivered_at")
    list_filter = ("currency", "agent")
    search_fields = ("provider_intention__property__name", "agent__first_name", "agent__last_name")
    raw_id_fields = ("provider_intention", "agent", "currency")
    readonly_fields = ("created_at", "updated_at")
