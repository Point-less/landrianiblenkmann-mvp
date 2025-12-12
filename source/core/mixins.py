from django.core.exceptions import PermissionDenied
from utils.authorization import check


class PermissionedViewMixin:
    """Mixin to enforce a required_action via utils.authorization.check."""

    required_action = None

    def dispatch(self, request, *args, **kwargs):
        if self.required_action is not None:
            check(request.user, self.required_action)
        return super().dispatch(request, *args, **kwargs)


__all__ = ["PermissionedViewMixin"]
