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


class ZonapropPublication(TimeStampedMixin):
    """Listing record synced from Zonaprop."""

    posting_id = models.PositiveBigIntegerField(unique=True)
    publisher_id = models.PositiveBigIntegerField()
    internal_code = models.CharField(max_length=64)
    begin_date = models.DateField()
    status = models.CharField(max_length=32)
    listing_payload = models.JSONField()

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Zonaprop publication"
        verbose_name_plural = "Zonaprop publications"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.internal_code} ({self.posting_id})"

    @property
    def is_active(self) -> bool:
        return self.status == "ONLINE"


class ZonapropPublicationDailyStat(TimeStampedMixin):
    """Daily statistics for a Zonaprop publication."""

    publication = models.ForeignKey(
        ZonapropPublication,
        on_delete=models.CASCADE,
        related_name="daily_stats",
    )
    date = models.DateField()
    impressions = models.PositiveIntegerField()
    views = models.PositiveIntegerField()
    leads = models.PositiveIntegerField()
    user_stats = models.JSONField(default=dict)

    class Meta:
        ordering = ("-date",)
        constraints = [
            models.UniqueConstraint(
                fields=("publication", "date"),
                name="unique_zonaprop_publication_day",
            ),
        ]


__all__ = [
    "TokkobrokerProperty",
    "ZonapropPublication",
    "ZonapropPublicationDailyStat",
]
