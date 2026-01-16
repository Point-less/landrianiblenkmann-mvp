"""Project-level middleware helpers."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse, JsonResponse

from utils.actors import actor_context

logger = logging.getLogger("django.request")


class ExceptionLoggingMiddleware:
    """Log unhandled exceptions with tracebacks to the console."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            return self.get_response(request)
        except Exception:
            logger.exception("Unhandled exception while processing request.")
            raise


class ActorContextMiddleware:
    """Bind the authenticated user to the execution context for auditing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        actor = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        with actor_context(actor):
            return self.get_response(request)


class RequireLoginMiddleware:
    """Enforce authenticated access for every request unless explicitly exempted."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = {
            path for path in map(self._normalize_path, getattr(settings, 'LOGIN_REQUIRED_EXEMPT_URLS', [])) if path
        }
        self.exempt_prefixes = tuple(
            path for path in map(self._normalize_path, getattr(settings, 'LOGIN_REQUIRED_EXEMPT_PREFIXES', [])) if path
        )
        self.login_url = getattr(settings, 'LOGIN_URL', '/admin/login/')

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated or self._is_exempt(request.path_info):
            return self.get_response(request)
        return self._unauthorized_response(request)

    def _is_exempt(self, path: str | None) -> bool:
        path = path or '/'
        if path in self.exempt_paths:
            return True
        return any(path.startswith(prefix) for prefix in self.exempt_prefixes)

    def _unauthorized_response(self, request: HttpRequest) -> HttpResponse:
        if self._prefers_json(request):
            return JsonResponse({'detail': 'Authentication required.'}, status=401)
        return redirect_to_login(request.get_full_path(), self.login_url)

    @staticmethod
    def _prefers_json(request: HttpRequest) -> bool:
        content_type = request.headers.get('content-type', '')
        accepts = request.headers.get('accept', '')
        return 'application/json' in accepts or 'application/json' in content_type or 'application/graphql' in content_type

    @staticmethod
    def _normalize_path(path: str | None) -> str | None:
        if not path:
            return None
        if not path.startswith('/'):
            path = f'/{path}'
        return path
