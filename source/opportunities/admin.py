from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path, reverse

from opportunities.models import TokkobrokerProperty
from opportunities.tasks import sync_tokkobroker_properties_task


@admin.register(TokkobrokerProperty)
class TokkobrokerPropertyAdmin(admin.ModelAdmin):
    list_display = ("tokko_id", "ref_code", "address", "tokko_created_at", "created_at")
    search_fields = ("tokko_id", "ref_code", "address")
    list_filter = ("tokko_created_at", "created_at")
    change_list_template = "admin/tokkobrokerproperty/change_list.html"

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

        if request.method == "POST":
            try:
                # adapt this to what your helper expects (all / missing / diff)
                processed = sync_tokkobroker_properties_task.send()
                self.message_user(request, f"Synced {processed} Tokkobroker properties.", level=messages.SUCCESS)
            except Exception as exc:
                self.message_user(request, f"Sync failed: {exc}", level=messages.ERROR)

            opts = self.model._meta
            return redirect(reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist"))

        # for GET just redirect back to changelist
        opts = self.model._meta
        return redirect(reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist"))
