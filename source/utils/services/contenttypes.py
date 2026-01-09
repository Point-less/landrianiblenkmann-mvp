from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from utils.services import BaseService


class ContentTypeForModelQuery(BaseService):
    atomic = False

    def run(self, *, obj):
        return ContentType.objects.get_for_model(obj, for_concrete_model=False)


__all__ = ["ContentTypeForModelQuery"]
