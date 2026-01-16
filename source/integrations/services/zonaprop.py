from __future__ import annotations

from datetime import date, datetime, timedelta

from django.db.models import Max

from integrations.models import ZonapropPublication, ZonapropPublicationDailyStat
from utils.services import BaseService


class ZonapropPublicationsQuery(BaseService):
    """Return Zonaprop publications with their latest stats date."""

    def run(self, *, actor=None):
        return ZonapropPublication.objects.annotate(
            latest_stat_date=Max("daily_stats__date"),
        ).order_by("-created_at")


class ZonapropPublicationDetailQuery(BaseService):
    """Return a single publication with its daily stats."""

    def run(self, *, actor=None, publication_id: int):
        return ZonapropPublication.objects.prefetch_related("daily_stats").get(
            pk=publication_id
        )


class UpsertZonapropPublicationService(BaseService):
    """Create or update a Zonaprop publication from listing payload."""

    def run(self, *, actor=None, item: dict) -> ZonapropPublication:
        internal_code = item.get("internalCode")
        posting_id = item.get("postingId")
        publisher_id = item.get("publisherId")
        url_posting = item.get("urlPosting")
        if not internal_code or not posting_id:
            raise RuntimeError("Missing internalCode or postingId in listing payload.")
        if not isinstance(publisher_id, int):
            raise RuntimeError("Missing publisherId in listing payload.")
        if not isinstance(url_posting, str) or not url_posting:
            raise RuntimeError("Missing urlPosting in listing payload.")
        if url_posting.startswith("http"):
            posting_url = url_posting
        else:
            posting_url = (
                "https://www.zonaprop.com.ar/propiedades/clasificado/"
                f"{url_posting.lstrip('/')}"
            )

        state_and_dates = item.get("stateAndDates")
        if not state_and_dates:
            raise RuntimeError(f"Missing stateAndDates for posting {posting_id}")

        begin_date_str = state_and_dates[0].get("beginDate")
        status = state_and_dates[0].get("status")
        if not begin_date_str or not status:
            raise RuntimeError(f"Missing beginDate or status for posting {posting_id}")

        begin_date = datetime.strptime(begin_date_str, "%d/%m/%Y").date()
        publication, _ = ZonapropPublication.objects.update_or_create(
            posting_id=posting_id,
            defaults={
                "internal_code": internal_code,
                "begin_date": begin_date,
                "status": status,
                "publisher_id": publisher_id,
                "posting_url": posting_url,
                "listing_payload": item,
            },
        )
        return publication


class ClearZonapropPublicationsService(BaseService):
    """Remove all Zonaprop publications and stats."""

    atomic = True

    def run(self, *, actor=None) -> int:
        deleted, _ = ZonapropPublication.objects.all().delete()
        return deleted


class NextZonapropStatsStartDateQuery(BaseService):
    """Compute the next stats start date for a publication."""

    def run(self, *, actor=None, publication: ZonapropPublication, end_date: date) -> date | None:
        if not publication.begin_date:
            raise RuntimeError(f"Publication {publication.posting_id} missing begin_date.")

        last_stat = publication.daily_stats.order_by("-date").first()
        start_date = (
            last_stat.date + timedelta(days=1)
            if last_stat
            else publication.begin_date
        )
        if start_date > end_date:
            return None
        return start_date


class StoreZonapropDailyStatsService(BaseService):
    """Store daily stats payload for a publication."""

    def run(self, *, actor=None, publication: ZonapropPublication, payload: dict) -> int:
        impressions = payload.get("impressions")
        views = payload.get("views")
        leads = payload.get("leads")
        user_stats = payload.get("userStat")
        if not all(isinstance(x, dict) for x in (impressions, views, leads, user_stats)):
            raise RuntimeError(
                f"Daily stats payload malformed for publication {publication.posting_id}"
            )

        rows = []
        for date_str, impression_value in impressions.items():
            if date_str not in views or date_str not in leads or date_str not in user_stats:
                raise RuntimeError(
                    f"Missing daily stats for {publication.posting_id} on {date_str}"
                )
            stat_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            rows.append(
                ZonapropPublicationDailyStat(
                    publication=publication,
                    date=stat_date,
                    impressions=int(impression_value),
                    views=int(views[date_str]),
                    leads=int(leads[date_str]),
                    user_stats=user_stats[date_str],
                )
            )

        if rows:
            ZonapropPublicationDailyStat.objects.bulk_create(
                rows,
                ignore_conflicts=True,
            )
        return len(rows)


__all__ = [
    "ZonapropPublicationsQuery",
    "ZonapropPublicationDetailQuery",
    "UpsertZonapropPublicationService",
    "ClearZonapropPublicationsService",
    "NextZonapropStatsStartDateQuery",
    "StoreZonapropDailyStatsService",
]

