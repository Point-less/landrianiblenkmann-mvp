from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from core.mixins import PermissionedViewMixin
from integrations.tasks import sync_tokkobroker_properties_task, sync_tokkobroker_registry
from utils.authorization import INTEGRATION_MANAGE


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
        from integrations.models import TokkobrokerProperty

        deleted, _ = TokkobrokerProperty.objects.all().delete()
        messages.warning(request, f'Cleared {deleted} Tokkobroker properties.')
        return self._redirect_back(request)

    def get(self, request):  # pragma: no cover
        return self._redirect_back(request)

    def _redirect_back(self, request):
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('workflow-dashboard-section', section='integrations')


__all__ = [
    "TokkoSyncRunView",
    "TokkoSyncEnqueueView",
    "TokkoClearView",
]
