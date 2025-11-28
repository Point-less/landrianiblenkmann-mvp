from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models.signals import pre_save
from django.dispatch import receiver
from django_fsm.signals import post_transition

from integrations.tasks import sync_marketing_package_publication_task
from opportunities.models import MarketingPackage


def _normalize_price(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(value)
    except (TypeError, ValueError):
        return None


@receiver(pre_save, sender=MarketingPackage)
def trigger_tokko_publication_on_price_change(sender, instance: MarketingPackage, **kwargs) -> None:
    """Trigger Tokkobroker publication sync when an active marketing package price changes."""

    if not instance.pk or instance.state != MarketingPackage.State.PUBLISHED:
        return
    print("trigger_tokko_publication_on_price_change", instance.pk)

    sync_marketing_package_publication_task.send(instance.pk)


@receiver(post_transition, sender=MarketingPackage)
def trigger_tokko_publication_on_state_change(
    sender,
    instance: MarketingPackage,
    target: str,
    **kwargs,
) -> None:
    """Trigger Tokkobroker publication sync when marketing package availability changes."""

    if target in {MarketingPackage.State.PUBLISHED, MarketingPackage.State.PAUSED}:
        sync_marketing_package_publication_task.send(instance.pk)
