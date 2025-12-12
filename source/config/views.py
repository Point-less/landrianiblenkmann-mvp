from django.shortcuts import render


def permission_denied(request, exception=None):  # pragma: no cover - simple render
    return render(request, '403.html', status=403)
