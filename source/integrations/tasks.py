"""Background tasks for integration workflows (e.g., Tokkobroker)."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, MutableMapping
from decimal import Decimal
from datetime import datetime

import dramatiq
from django.conf import settings

from integrations.models import TokkobrokerProperty
from integrations.tokkobroker import (
    TokkoAuthenticationError,
    TokkoClient,
    TokkoIntegrationError,
    fetch_tokkobroker_properties,
)
from opportunities.models import MarketingPackage
from utils.services import S

logger = logging.getLogger(__name__)


def _parse_tokkobroker_date(raw: str | None) -> datetime.date | None:
    if not raw:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    logger.debug("Unable to parse Tokkobroker date '%s'", raw)
    return None


def _extract_created_at(payload: Mapping[str, object]) -> str | None:
    quick_data = payload.get("quick_data")
    if isinstance(quick_data, Mapping):
        data = quick_data.get("data")
        if isinstance(data, Mapping):
            created_at = data.get("created_at")
            if isinstance(created_at, str):
                return created_at
    return None


def sync_tokkobroker_registry(
    payloads: Iterable[MutableMapping[str, object]] | None = None,
) -> int:
    """Synchronize the Tokkobroker property registry.

    Returns the number of records processed.
    """

    if payloads is None:
        payloads = fetch_tokkobroker_properties()
    count = 0

    for payload in payloads:
        if not isinstance(payload, MutableMapping):
            logger.debug("Skipping malformed Tokkobroker payload: %r", payload)
            continue

        tokko_id = payload.get("id")
        ref_code = payload.get("ref_code")
        address = payload.get("address")
        created_at_raw = _extract_created_at(payload)

        if not isinstance(tokko_id, int):
            logger.debug("Skipping Tokkobroker payload without integer 'id': %r", payload)
            continue

        defaults = {
            "ref_code": str(ref_code or ""),
            "address": str(address or ""),
            "tokko_created_at": _parse_tokkobroker_date(created_at_raw),
        }

        TokkobrokerProperty.objects.update_or_create(
            tokko_id=tokko_id,
            defaults=defaults,
        )
        count += 1

    return count


@dramatiq.actor
def sync_tokkobroker_properties_task() -> None:
    processed = sync_tokkobroker_registry()
    logger.info("Synced %s Tokkobroker properties", processed)


def _format_tokko_price(price: Decimal) -> str:
    return str(price.quantize(Decimal()))


def _publish_marketing_package(client: TokkoClient, marketing_package: MarketingPackage, property_id: int) -> None:
    price = marketing_package.price
    currency = marketing_package.currency.code.upper() if marketing_package.currency else None

    if price is None:
        logger.warning("Cannot publish marketing package %s without price", marketing_package.pk)
        return

    if currency != "USD":
        logger.info(
            "Skipping Tokkobroker price sync for marketing package %s due to unsupported currency %s",
            marketing_package.pk,
            currency or "unset",
        )
        return

    try:
        response = client.call_property_endpoint(
            property_id,
            {"OP-1-ENA": "true"},
            action="enable publication",
        )
    except TokkoIntegrationError:
        logger.exception(
            "Tokkobroker enable publication request failed for marketing package %s",
            marketing_package.pk,
        )
        return

    if response.status_code != 200:
        logger.warning(
            "Tokkobroker enable publication request for marketing package %s (property=%s) returned %s",
            marketing_package.pk,
            property_id,
            response.status_code,
        )
        return

    price_value = _format_tokko_price(price)
    try:
        response = client.call_property_endpoint(
            property_id,
            {"OP-1-primary": price_value},
            action="price update",
        )
    except TokkoIntegrationError:
        logger.exception(
            "Tokkobroker price update request failed for marketing package %s",
            marketing_package.pk,
        )
        return

    if response.status_code != 200:
        logger.warning(
            "Tokkobroker price update request for marketing package %s (property=%s) returned %s",
            marketing_package.pk,
            property_id,
            response.status_code,
        )
        return

    logger.info(
        "Tokkobroker price updated for marketing package %s (property=%s price=%s USD)",
        marketing_package.pk,
        property_id,
        price_value,
    )


def _unpublish_marketing_package(client: TokkoClient, marketing_package: MarketingPackage, property_id: int) -> None:
    try:
        response = client.call_property_endpoint(
            property_id,
            {"OP-1-ENA": "false"},
            action="disable publication",
        )
    except TokkoIntegrationError:
        logger.exception(
            "Tokkobroker disable publication request failed for marketing package %s",
            marketing_package.pk,
        )
        return

    if response.status_code != 200:
        logger.warning(
            "Tokkobroker disable publication request for marketing package %s (property=%s) returned %s",
            marketing_package.pk,
            property_id,
            response.status_code,
        )
        return

    logger.info(
        "Tokkobroker publication disabled for marketing package %s (property=%s)",
        marketing_package.pk,
        property_id,
    )


@dramatiq.actor
def sync_marketing_package_publication_task(marketing_package_id: int) -> None:
    """Ensure Tokkobroker reflects the marketing package publication status."""

    if not settings.TOKKO_SYNC_ENABLED:
        logger.info(
            "Tokkobroker sync disabled; skipping marketing package %s publication task",
            marketing_package_id,
        )
        return

    try:
        marketing_package = S.opportunities.MarketingPackageByIdQuery(pk=marketing_package_id)
    except MarketingPackage.DoesNotExist:
        logger.warning(
            "Marketing package %s not found while preparing Tokkobroker sync",
            marketing_package_id,
        )
        return

    try:
        client = TokkoClient(base_url=settings.TOKKO_BASE_URL, timeout=settings.TOKKO_TIMEOUT)
        client.authenticate(
            username=settings.TOKKO_USERNAME,
            password=settings.TOKKO_PASSWORD,
            token=settings.TOKKO_OTP_TOKEN,
        )
    except TokkoAuthenticationError:
        logger.exception(
            "Tokkobroker authentication failed while handling marketing package %s publication sync",
            marketing_package_id,
        )
        return

    logger.debug("Authenticated Tokkobroker client ready for marketing package %s", marketing_package_id)

    is_active = marketing_package.state == MarketingPackage.State.AVAILABLE
    action = "publish" if is_active else "unpublish" if marketing_package.state == MarketingPackage.State.PAUSED else "skip"

    if action == "skip":
        logger.info(
            "Tokkobroker sync skipped for marketing package %s (state=%s)",
            marketing_package_id,
            marketing_package.state,
        )
        return

    opportunity = marketing_package.opportunity
    tokko_property = getattr(opportunity, "tokkobroker_property", None)
    if not tokko_property:
        logger.warning(
            "Tokkobroker property missing for marketing package %s; cannot sync",
            marketing_package.pk,
        )
        return

    property_id = tokko_property.tokko_id

    logger.info(
        "Tokkobroker sync requested to %s marketing package %s (price=%s currency=%s)",
        action,
        marketing_package_id,
        marketing_package.price,
        marketing_package.currency or "unset",
    )
    if action == "publish":
        _publish_marketing_package(client, marketing_package, property_id)
    elif action == "unpublish":
        _unpublish_marketing_package(client, marketing_package, property_id)


__all__ = [
    "sync_tokkobroker_registry",
    "sync_tokkobroker_properties_task",
    "sync_marketing_package_publication_task",
]
