from django.db import models

from utils.mixins import TimeStampedMixin


class Currency(TimeStampedMixin):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10, blank=True)

    class Meta:
        ordering = ("code",)
        verbose_name = "currency"
        verbose_name_plural = "currencies"

    def __str__(self) -> str:
        return self.code


__all__ = ["Currency"]
