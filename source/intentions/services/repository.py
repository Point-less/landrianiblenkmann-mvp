"""Repository helpers to decouple intentions from opportunity models."""

from django.core.exceptions import ObjectDoesNotExist


class IntentionRepository:
    def has_provider_opportunity(self, intention) -> bool:
        try:
            intention.provider_opportunity  # type: ignore[attr-defined]
        except ObjectDoesNotExist:
            return False
        return True

    def has_seeker_opportunity(self, intention) -> bool:
        try:
            intention.seeker_opportunity  # type: ignore[attr-defined]
        except ObjectDoesNotExist:
            return False
        return True


__all__ = ["IntentionRepository"]
