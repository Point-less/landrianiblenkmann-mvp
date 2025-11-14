from __future__ import annotations

from django.db import models

from utils.mixins import TimeStampedMixin


class TokkobrokerProperty(TimeStampedMixin):
    """Minimal registry entry for Tokkobroker-sourced properties."""

    tokko_id = models.PositiveIntegerField(unique=True)
    ref_code = models.CharField(max_length=64)
    address = models.CharField(max_length=255, blank=True)
    tokko_created_at = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Tokkobroker property"
        verbose_name_plural = "Tokkobroker properties"
        db_table = 'core_tokkobrokerproperty'

    def __str__(self) -> str:  # pragma: no cover - human readable helper
        return f"{self.ref_code} ({self.tokko_id})"


__all__ = ["TokkobrokerProperty"]
