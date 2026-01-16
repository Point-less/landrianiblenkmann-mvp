from django.contrib import messages
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView, TemplateView
from django.http import JsonResponse
from django.db.models import Q, Sum

from core.mixins import PermissionedViewMixin
from integrations.tasks import (
    sync_tokkobroker_properties_task,
    sync_tokkobroker_registry,
    sync_zonaprop_publications_task,
    sync_zonaprop_registry,
)
from utils.authorization import INTEGRATION_MANAGE, INTEGRATION_VIEW
from utils.services import S


class TokkoSyncRunView(PermissionedViewMixin, LoginRequiredMixin, View):
    login_url = '/admin/login/'
    required_action = INTEGRATION_MANAGE

    def post(self, request):
        if getattr(settings, "TOKKO_DISABLE_SYNC", False):
            messages.info(request, "Tokkobroker sync skipped (disabled in settings).")
        else:
            processed = sync_tokkobroker_registry()
            messages.success(request, f'Synced {processed} Tokkobroker properties.')
        return self._redirect_back(request)

    def get(self, request):  # pragma: no cover - redirect to avoid GET usage
        return self._redirect_back(request)

    def _redirect_back(self, request):
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('workflow-dashboard-section', section='integrations')


class TokkoPropertySearchView(LoginRequiredMixin, ListView):
    http_method_names = ["get"]
    paginate_by = 20

    def get_queryset(self):
        q = self.request.GET.get("term", self.request.GET.get("q", "")).strip()
        queryset = S.core.AvailableTokkobrokerPropertiesQuery(actor=self.request.user)
        if q:
            queryset = queryset.filter(
                Q(ref_code__icontains=q)
                | Q(address__icontains=q)
                | Q(tokko_id__icontains=q)
            )
        return queryset.order_by("-tokko_id")

    def render_to_response(self, context, **response_kwargs):
        page = int(self.request.GET.get("page", "1") or 1)
        start = (page - 1) * self.paginate_by
        end = start + self.paginate_by
        qs = context["object_list"]
        total = qs.count()
        results = list(qs[start:end])
        more = total > end

        payload = {
            "results": [
                {
                    "id": obj.pk,
                    "text": f"{obj.ref_code or 'No ref'} (ID {obj.tokko_id}) — {obj.address}".strip(),
                }
                for obj in results
            ],
            "pagination": {"more": more},
        }
        return JsonResponse(payload)


class TokkoSyncEnqueueView(PermissionedViewMixin, LoginRequiredMixin, View):
    login_url = '/admin/login/'
    required_action = INTEGRATION_MANAGE

    def post(self, request):
        message = sync_tokkobroker_properties_task.send()
        messages.info(request, f'Tokkobroker sync enqueued (message ID: {message.message_id}).')
        return self._redirect_back(request)

    def get(self, request):  # pragma: no cover
        return self._redirect_back(request)

    def _redirect_back(self, request):
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('workflow-dashboard-section', section='integrations')


class TokkoClearView(PermissionedViewMixin, LoginRequiredMixin, View):
    login_url = '/admin/login/'
    required_action = INTEGRATION_MANAGE

    def post(self, request):
        deleted = S.integrations.ClearTokkobrokerRegistryService()
        messages.warning(request, f'Cleared {deleted} Tokkobroker properties.')
        return self._redirect_back(request)

    def get(self, request):  # pragma: no cover
        return self._redirect_back(request)

    def _redirect_back(self, request):
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('workflow-dashboard-section', section='integrations')


class ZonapropSyncRunView(PermissionedViewMixin, LoginRequiredMixin, View):
    login_url = '/admin/login/'
    required_action = INTEGRATION_MANAGE

    def post(self, request):
        processed = sync_zonaprop_registry()
        messages.success(request, f"Zonaprop publications synced ({processed}).")
        return self._redirect_back(request)

    def get(self, request):  # pragma: no cover - redirect to avoid GET usage
        return self._redirect_back(request)

    def _redirect_back(self, request):
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('workflow-dashboard-section', section='integration-zonaprop')


class ZonapropSyncEnqueueView(PermissionedViewMixin, LoginRequiredMixin, View):
    login_url = '/admin/login/'
    required_action = INTEGRATION_MANAGE

    def post(self, request):
        message = sync_zonaprop_publications_task.send()
        messages.info(
            request,
            f"Zonaprop sync enqueued (message ID: {message.message_id}).",
        )
        return self._redirect_back(request)

    def get(self, request):  # pragma: no cover - redirect to avoid GET usage
        return self._redirect_back(request)

    def _redirect_back(self, request):
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('workflow-dashboard-section', section='integration-zonaprop')


class ZonapropClearView(PermissionedViewMixin, LoginRequiredMixin, View):
    login_url = '/admin/login/'
    required_action = INTEGRATION_MANAGE

    def post(self, request):
        deleted = S.integrations.ClearZonapropPublicationsService()
        messages.warning(request, f"Cleared {deleted} Zonaprop publications.")
        return self._redirect_back(request)

    def get(self, request):  # pragma: no cover
        return self._redirect_back(request)

    def _redirect_back(self, request):
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('workflow-dashboard-section', section='integration-zonaprop')


class ZonapropPublicationDetailView(PermissionedViewMixin, LoginRequiredMixin, TemplateView):
    login_url = '/admin/login/'
    template_name = "workflow/zonaprop_publication_detail.html"
    required_action = INTEGRATION_VIEW

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        publication = S.integrations.ZonapropPublicationDetailQuery(
            actor=self.request.user,
            publication_id=self.kwargs["publication_id"],
        )
        context["publication"] = publication
        daily_stats = publication.daily_stats.order_by("date")
        chart_rows = list(
            daily_stats.values_list("date", "impressions", "views", "leads")
        )
        context["chart_labels"] = [row[0].isoformat() for row in chart_rows]
        context["chart_impressions"] = [row[1] for row in chart_rows]
        context["chart_views"] = [row[2] for row in chart_rows]
        context["chart_leads"] = [row[3] for row in chart_rows]
        totals = daily_stats.aggregate(
            impressions=Sum("impressions"),
            views=Sum("views"),
            leads=Sum("leads"),
        )
        context["daily_stats"] = daily_stats
        context["daily_totals"] = totals
        context["current_url"] = self.request.get_full_path()
        return context


__all__ = [
    "TokkoSyncRunView",
    "TokkoSyncEnqueueView",
    "TokkoClearView",
    "ZonapropSyncRunView",
    "ZonapropSyncEnqueueView",
    "ZonapropClearView",
    "ZonapropPublicationDetailView",
]
