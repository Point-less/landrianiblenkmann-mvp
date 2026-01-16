#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch all postings from Zonaprop and store one JSON file per posting id
including the posting data, summary stats, and daily stats.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from etc.test_zp_fetching_listings import EMAIL, PASSWORD
from integrations.zonaprop_client import ZonapropClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "zonaprop_postings"


def main() -> None:
    email = os.environ.get("ZP_EMAIL", EMAIL)
    password = os.environ.get("ZP_PASSWORD", PASSWORD)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client = ZonapropClient(email=email, password=password)
    client.login()

    page = 1
    max_page = 1
    total_postings = 0
    today = datetime.today().date()

    while page <= max_page:
        response = client.fetch_postings(page=page)
        postings = response["postings"]
        max_page = response["maxPage"]
        total_postings = response["count"]
        logger.info("Fetched page %s/%s with %s postings", page, max_page, len(postings))

        for item in postings:
            posting_id = int(item["postingId"])
            state_and_dates = item.get("stateAndDates")
            if not state_and_dates:
                raise RuntimeError(f"stateAndDates missing for posting {posting_id}")
            begin_date_str = state_and_dates[0].get("beginDate")
            if not begin_date_str:
                raise RuntimeError(f"beginDate missing for posting {posting_id}")

            start_date = datetime.strptime(begin_date_str, "%d/%m/%Y").date()
            summary = client.fetch_posting_summary(
                posting_id, start_date=start_date, end_date=today
            )
            daily = client.fetch_posting_daily_stats(
                posting_id, start_date=start_date, end_date=today
            )

            payload = {
                "posting": item,
                "summary": summary,
                "daily": daily,
            }

            output_path = OUTPUT_DIR / f"{posting_id}.json"
            with output_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=True, indent=2)

        page += 1

    logger.info("Finished. Stored %s postings.", total_postings)


if __name__ == "__main__":
    main()

