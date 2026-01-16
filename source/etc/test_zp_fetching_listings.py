#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple script that logs in to zonaprop, fetches the postings list and then
fetches the statistics for each posting (days=30). Uses an in-memory requests.Session().
"""

import logging
import requests
import time
import re
from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta

EMAIL = "consultasinmobiliarialb@gmail.com"
PASSWORD = "zona123"

BASE = "https://www.zonaprop.com.ar"
PRE_LOGIN_URL = f"{BASE}/rp-api/user/{EMAIL}"
LOGIN_URL = f"{BASE}/login_login.ajax"
GET_SESSION = "https://www.zonaprop.com.ar/rp-api/user/session"
POSTINGS_URL = f"{BASE}/avisos-api/panel/api/v2/postings"
STAT_URL_TEMPLATE = f"{BASE}/avisos-api/panel/api/v1/statistic/posting/{{posting_id}}"
STAT_DAILY_URL_TEMPLATE = f"{BASE}/avisos-api/panel/api/v1/statistic/posting/daily/{{posting_id}}"

# Replace with real credentials


# Small delay between requests (seconds)
REQUEST_DELAY = 0.15

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def get_posting_list_from_json(j: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """Try common keys and heuristics to find the list of postings in the JSON response."""
    candidates = ["postings", "items", "results", "data", "rows"]
    for k in candidates:
        v = j.get(k)
        if isinstance(v, list):
            return v
    # fallback: return first list found at top level
    for v in j.values():
        if isinstance(v, list):
            return v
    return None


def get_posting_id(item: Dict[str, Any]) -> Optional[int]:
    """Attempt to extract a posting id from an item using common keys / patterns."""
    # direct keys
    for key in ("id", "postingId", "posting_id", "postId", "adId"):
        if key in item:
            val = item[key]
            if isinstance(val, int):
                return val
            # sometimes id is stringified
            if isinstance(val, str) and val.isdigit():
                return int(val)

    # nested
    if isinstance(item.get("posting"), dict) and "id" in item["posting"]:
        p = item["posting"]["id"]
        if isinstance(p, int):
            return p
        if isinstance(p, str) and p.isdigit():
            return int(p)

    # look for integers in values (last resort)
    for v in item.values():
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)

    # regex fallback: check urls or strings that may contain the id
    for v in item.values():
        if isinstance(v, str):
            m = re.search(r"/(\d{5,12})\b", v)  # match a 5-12 digit id in a path or query
            if m:
                return int(m.group(1))

    return None


def log_request_response(label: str, response: requests.Response) -> None:
    req = response.request
    logger.info("%s request: %s %s", label, req.method, req.url)
    if req.headers:
        logger.info("%s request headers: %s", label, dict(req.headers))
    if req.body:
        body = req.body
        if isinstance(body, bytes):
            body = body.decode(errors="replace")
        logger.info("%s request body: %s", label, body)
    logger.info("%s response status: %s", label, response.status_code)
    logger.info("%s response headers: %s", label, dict(response.headers))
    logger.info("%s response text (truncated): %s", label, response.text[:1000])


def iter_month_ranges(start_date: date, end_date: date) -> List[tuple[date, date]]:
    ranges: List[tuple[date, date]] = []
    current = date(start_date.year, start_date.month, 1)
    while current <= end_date:
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = next_month - timedelta(days=1)
        range_start = max(start_date, current)
        range_end = min(end_date, month_end)
        ranges.append((range_start, range_end))
        current = next_month
    return ranges


def merge_daily_stats(
    aggregated: Dict[str, Any],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    for key, value in payload.items():
        if key == "period":
            if value is not None:
                aggregated["period"] = value
            continue
        if isinstance(value, dict):
            aggregated.setdefault(key, {})
            aggregated[key].update(value)
        else:
            aggregated[key] = value
    return aggregated


def main():
    logger.info("Starting Zonaprop fetch flow")
    s = requests.Session()
    # Useful top-level headers; requests Session will send cookies automatically for the domain
    s.headers.update({
        "Accept": "*/*",
        "Accept-Language": "en",
        # Keep Content-Type here; requests will set it automatically for form-encoded POST,
        # but having it matches your browser fetch more closely.
        #"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.zonaprop.com.ar/",
        "Origin": "https://www.zonaprop.com.ar",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.7258.138 Safari/537.36",
    })

    # 1) prime the site (get initial cookies) — sometimes required
    logger.info("Stage 1: Prime session cookies")
    try:
        r0 = s.get(BASE, timeout=10)
        log_request_response("Prime", r0)
    except Exception as e:
        logger.warning("Initial GET failed: %s", e)


    pre_login_data = {
        "username": EMAIL,
        "origin": "Botón Ingresar"
    }

    logger.info("Stage 2: Pre-login")
    try:
        r = s.post(PRE_LOGIN_URL, timeout=10, json=pre_login_data)
        log_request_response("Pre-login", r)
        r.raise_for_status()
    except Exception as e:
        logger.error("Pre-login request failed: %s", e)
        logger.error("Pre-login response: %s", r.content if "r" in locals() else "(no response)")
        return

    # 2) login (form encoded)
    payload = {
        "email": EMAIL,
        "password": PASSWORD,
        "recordarme": "true",
        "homeSeeker": "true",
        "urlActual": "https://www.zonaprop.com.ar",
    }

    logger.info("Stage 3: Login")
    try:
        r = s.post(LOGIN_URL, data=payload, timeout=15)
        log_request_response("Login", r)
        r.raise_for_status()
    except Exception as e:
        logger.error("Login request failed: %s", e)
        return

    # Attach sessionId header from cookie (if present) so subsequent API
    # requests include the session identifier as a header.
    session_cookie = s.cookies.get("sessionId")
    if session_cookie:
        s.headers["sessionId"] = session_cookie

    logger.info("Stage 4: Get session")
    try:
        r_session = s.get(GET_SESSION, timeout=15)
        log_request_response("Get session", r_session)
        r_session.raise_for_status()
    except Exception as e:
        logger.error("Get session request failed: %s", e)
        return

    # 4) fetch postings (page=1, limit=20, sort:modifiedNewer, onlineFirst=true)
    logger.info("Stage 5: Fetch postings")
    params = {
        "page": 1,
        "limit": 1000,
        #"searchParameters": "sort:modifiedNewer",
        "searchParameters": "status:ONLINE;sort:modifiedNewer",
        "onlineFirst": "true",
    }

    headers = {
        "x-panel-portal": "ZPAR",
    }

    try:
        r2 = s.get(POSTINGS_URL, params=params, timeout=15, headers=headers)
        log_request_response("Postings", r2)
        r2.raise_for_status()
    except Exception as e:
        logger.error("Failed to fetch postings: %s", e)
        if "r2" in locals():
            logger.error("Postings response: %s", r2.content)
            logger.error("Postings request headers: %s", r2.request.headers)
        return

    try:
        postings_json = r2.json()
    except ValueError:
        logger.error("Postings endpoint did not return valid JSON")
        logger.error("Postings response text (truncated): %s", r2.text[:1000])
        return

    postings = get_posting_list_from_json(postings_json)
    if postings is None:
        logger.error(
            "Could not find a postings list in response JSON. Top-level keys=%s",
            list(postings_json.keys()),
        )
        return


    logger.info("Fetching stats for %s postings", len(postings))
    stats_by_posting = {}
    end_date = datetime.today().date()
    for idx, item in enumerate(postings, start=1):
        posting_id = get_posting_id(item)
        begin_date = datetime.strptime(
            item["stateAndDates"][0]["beginDate"], "%d/%m/%Y"
        ).date()

        if posting_id is None:
            logger.warning(
                "[%s] Could not determine posting id for item: keys=%s",
                idx,
                list(item.keys()),
            )
            continue

        params = {
            "days": 0,
            "startPeriod": begin_date.strftime("%Y-%m-%d"),
            "endPeriod": end_date.strftime("%Y-%m-%d"),
        }


        stat_url = STAT_URL_TEMPLATE.format(posting_id=posting_id)
        headers = {
            "x-panel-portal": "ZPAR",
        }
        logger.info("[%s/%s] Stage stats fetch for posting_id=%s", idx, len(postings), posting_id)
        try:
            r_stat = s.get(stat_url, timeout=15, headers=headers, params=params)
            log_request_response(f"Stats[{idx}]", r_stat)
            r_stat.raise_for_status()
        except Exception as e:
            logger.error(
                "[%s] Failed to fetch stats for posting %s: %s",
                idx,
                posting_id,
                e,
            )


        summary_stats = r_stat.json()

        daily_stats_url = STAT_DAILY_URL_TEMPLATE.format(posting_id=posting_id)
        daily_stats: Dict[str, Any] = {}
        for range_start, range_end in iter_month_ranges(begin_date, end_date):
            daily_params = {
                "days": 0,
                "startPeriod": range_start.strftime("%Y-%m-%d"),
                "endPeriod": range_end.strftime("%Y-%m-%d"),
            }
            logger.info(
                "[%s/%s] Stage daily stats fetch for posting_id=%s (%s to %s)",
                idx,
                len(postings),
                posting_id,
                daily_params["startPeriod"],
                daily_params["endPeriod"],
            )
            try:
                r_daily = s.get(daily_stats_url, timeout=15, headers=headers, params=daily_params)
                log_request_response(f"DailyStats[{idx}]", r_daily)
                r_daily.raise_for_status()
            except Exception as e:
                logger.error(
                    "[%s] Failed to fetch daily stats for posting %s (%s to %s): %s",
                    idx,
                    posting_id,
                    daily_params["startPeriod"],
                    daily_params["endPeriod"],
                    e,
                )
                continue

            daily_stats = merge_daily_stats(daily_stats, r_daily.json())
            time.sleep(REQUEST_DELAY)

        stats_by_posting[posting_id] = {
            "info": item,
            "summary": summary_stats,
            "daily": daily_stats,
        }

        time.sleep(REQUEST_DELAY)
        break

    logger.info("Finished fetching stats; collected %s postings", len(stats_by_posting))
    # Optional: return mapping if script is imported
    return stats_by_posting


if __name__ == "__main__":
    print(main())
