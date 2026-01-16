from __future__ import annotations

from datetime import date
from django.test import TestCase, override_settings

from integrations.models import ZonapropPublication, ZonapropPublicationDailyStat
from integrations.services.zonaprop import (
    ClearZonapropPublicationsService,
    NextZonapropStatsStartDateQuery,
    StoreZonapropDailyStatsService,
    UpsertZonapropPublicationService,
    ZonapropPublicationDetailQuery,
    ZonapropPublicationsQuery,
)


@override_settings(BYPASS_SERVICE_AUTH_FOR_TESTS=True)
class ZonapropServiceTests(TestCase):
    def setUp(self):
        self.postings_payload = {
            "postings": [
                {
                    "postingId": 1,
                    "publisherId": 555,
                    "urlPosting": "casa-en-cinco-saltos-57712278.html",
                    "internalCode": "A-1",
                    "stateAndDates": [{"status": "ONLINE", "beginDate": "01/01/2026"}],
                },
                {
                    "postingId": 2,
                    "internalCode": "B-2",
                    "urlPosting": "casa-offline-57712279.html",
                    "stateAndDates": [{"status": "OFFLINE", "beginDate": "02/01/2026"}],
                },
            ],
            "count": 2,
            "minPage": 1,
            "currentPage": 1,
            "maxPage": 1,
        }
        self.daily_payload = {
            "impressions": {"2026-01-02": 10},
            "views": {"2026-01-02": 5},
            "leads": {"2026-01-02": 1},
            "userStat": {"2026-01-02": {"total": 1}},
        }

    def test_services_create_publications_and_stats(self):
        for item in self.postings_payload["postings"]:
            UpsertZonapropPublicationService(item=item)

        self.assertEqual(ZonapropPublication.objects.count(), 2)
        active = ZonapropPublication.objects.get(posting_id=1)
        inactive = ZonapropPublication.objects.get(posting_id=2)
        self.assertEqual(active.status, "ONLINE")
        self.assertEqual(inactive.status, "OFFLINE")
        self.assertEqual(active.publisher_id, 555)
        self.assertEqual(
            active.posting_url,
            "https://www.zonaprop.com.ar/propiedades/clasificado/casa-en-cinco-saltos-57712278.html",
        )

        start_date = NextZonapropStatsStartDateQuery(
            publication=active,
            end_date=date(2026, 1, 2),
        )
        self.assertEqual(start_date, date(2026, 1, 1))

        created = StoreZonapropDailyStatsService(
            publication=active,
            payload=self.daily_payload,
        )
        self.assertEqual(created, 1)
        self.assertEqual(ZonapropPublicationDailyStat.objects.count(), 1)

    def test_publications_query_returns_latest_stat(self):
        publication = ZonapropPublication.objects.create(
            posting_id=10,
            publisher_id=999,
            internal_code="CODE-10",
            posting_url="https://www.zonaprop.com/casa-10.html",
            begin_date=date(2026, 1, 1),
            status="ONLINE",
            listing_payload={"postingId": 10},
        )
        ZonapropPublicationDailyStat.objects.create(
            publication=publication,
            date=date(2026, 1, 2),
            impressions=1,
            views=1,
            leads=0,
            user_stats={"total": 1},
        )
        results = list(ZonapropPublicationsQuery())
        self.assertEqual(results[0].latest_stat_date, date(2026, 1, 2))

    def test_publication_detail_query(self):
        publication = ZonapropPublication.objects.create(
            posting_id=11,
            publisher_id=1001,
            internal_code="CODE-11",
            posting_url="https://www.zonaprop.com/casa-11.html",
            begin_date=date(2026, 1, 1),
            status="ONLINE",
            listing_payload={"postingId": 11},
        )
        result = ZonapropPublicationDetailQuery(publication_id=publication.id)
        self.assertEqual(result.posting_id, 11)

    def test_clear_publications_service(self):
        ZonapropPublication.objects.create(
            posting_id=20,
            publisher_id=2000,
            internal_code="CODE-20",
            posting_url="https://www.zonaprop.com/casa-20.html",
            begin_date=date(2026, 1, 1),
            status="ONLINE",
            listing_payload={"postingId": 20},
        )
        deleted = ClearZonapropPublicationsService()
        self.assertGreaterEqual(deleted, 1)
        self.assertEqual(ZonapropPublication.objects.count(), 0)

