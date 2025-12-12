from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from integrations.models import TokkobrokerProperty
from integrations.tasks import sync_tokkobroker_properties_task, sync_tokkobroker_registry
from opportunities.models import OperationAgreement


@admin.register(TokkobrokerProperty)
class TokkobrokerPropertyAdmin(admin.ModelAdmin):
    list_display = ("tokko_id", "ref_code", "address", "tokko_created_at", "created_at")
    search_fields = ("tokko_id", "ref_code", "address")
    list_filter = ("tokko_created_at", "created_at")
    change_list_template = "admin/tokkobrokerproperty/change_list.html"
    actions = ("sync_from_tokkobroker_action",)

    def changelist_view(self, request, extra_context=None):
        extra_context = dict(extra_context or {})
        extra_context["has_change_permission"] = self.has_change_permission(request)
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        opts = self.model._meta
        custom_urls = [
            path(
                "sync-all/",
                self.admin_site.admin_view(self.sync_all),
                name=f"{opts.app_label}_{opts.model_name}_sync_all",
            ),
        ]

        return custom_urls + super().get_urls()

    def sync_all(self, request):
        # permission check (admin_view + this is defensive)
        if not self.has_change_permission(request):
            return self.permission_denied(request)

        opts = self.model._meta
        changelist_url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")

        if request.method == "POST":
            try:
                message = sync_tokkobroker_properties_task.send()
                self.message_user(
                    request,
                    f"Tokkobroker sync enqueued (message ID: {message.message_id}).",
                    level=messages.SUCCESS,
                )
            except Exception as exc:
                self.message_user(request, f"Sync failed: {exc}", level=messages.ERROR)

            return redirect(changelist_url)

        context = {
            **self.admin_site.each_context(request),
            "opts": opts,
            "app_label": opts.app_label,
            "title": "Confirm Tokkobroker sync",
            "changelist_url": changelist_url,
        }
        return TemplateResponse(request, "admin/tokkobrokerproperty/sync_all_confirm.html", context)

    def sync_from_tokkobroker_action(self, request, queryset):
        processed = sync_tokkobroker_registry()
        self.message_user(request, f"Synced {processed} Tokkobroker properties.")

    sync_from_tokkobroker_action.short_description = "Sync Tokkobroker registry now"


@admin.register(OperationAgreement)
class OperationAgreementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "provider_opportunity",
        "seeker_opportunity",
        "state",
        "created_at",
    )
    list_filter = ("state", "created_at")
    search_fields = (
        "provider_opportunity__source_intention__property__address__full_address",
        "seeker_opportunity__source_intention__contact__first_name",
        "seeker_opportunity__source_intention__contact__last_name",
    )
    readonly_fields = ("created_at", "updated_at", "agreed_at", "signed_at", "cancelled_at")
