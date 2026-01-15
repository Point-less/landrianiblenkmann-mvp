#!/usr/bin/env python3
"""
Simple script that logs in to zonaprop, fetches the postings list and then
fetches the statistics for each posting (days=30). Uses an in-memory requests.Session().
"""

import requests
import time
import re
from typing import Any, Dict, List, Optional

EMAIL = "consultasinmobiliarialb@gmail.com"
PASSWORD = "zona123"

BASE = "https://www.zonaprop.com.ar"
PRE_LOGIN_URL = f"{BASE}/rp-api/user/{EMAIL}"
LOGIN_URL = f"{BASE}/login_login.ajax"
POSTINGS_URL = f"{BASE}/avisos-api/panel/api/v2/postings"
STAT_URL_TEMPLATE = f"{BASE}/avisos-api/panel/api/v1/statistic/posting/{{posting_id}}?days=30"

# Replace with real credentials


# Small delay between requests (seconds)
REQUEST_DELAY = 0.15


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


def main():
    s = requests.Session()
    # Useful top-level headers; requests Session will send cookies automatically for the domain
    s.headers.update({
        "Accept": "*/*",
        "Accept-Language": "en",
        # Keep Content-Type here; requests will set it automatically for form-encoded POST,
        # but having it matches your browser fetch more closely.
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.zonaprop.com.ar/",
        "Origin": "https://www.zonaprop.com.ar",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.7258.138 Safari/537.36",
    })

    # 1) prime the site (get initial cookies) — sometimes required
    try:
        s.get(BASE, timeout=10)
    except Exception as e:
        print("Warning: initial GET failed:", e)

    try:
        r = s.post(PRE_LOGIN_URL, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(r.content)
        print("Pre-login request failed:", e)
        return

    # 2) login (form encoded)
    payload = {
        "email": EMAIL,
        "password": PASSWORD,
        "recordarme": "true",
        "homeSeeker": "true",
        "urlActual": "https://www.zonaprop.com.ar",
    }

    try:
        r = s.post(LOGIN_URL, data=payload, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print("Login request failed:", e)
        return

    # Inspect login response
    try:
        login_json = r.json()
        print("Login response (json):", login_json)
    except ValueError:
        print("Login response (text):", (r.text or "")[:400])

    # Attach sessionId header from cookie (if present) so subsequent API
    # requests include the session identifier as a header.
    session_cookie = s.cookies.get("sessionId")
    if session_cookie:
        s.headers["sessionId"] = session_cookie

    # 3) fetch postings (page=1, limit=20, sort:modifiedNewer, onlineFirst=true)
    params = {
        "page": 1,
        "limit": 20,
        "searchParameters": "sort:modifiedNewer",
        "onlineFirst": "true",
    }

    try:
        r2 = s.get(POSTINGS_URL, params=params, timeout=15)
        r2.raise_for_status()
    except Exception as e:
        
        print("Failed to fetch postings:", e)
        print(r2.content)
        print(r2.request.headers)
        return

    try:
        postings_json = r2.json()
    except ValueError:
        print("Postings endpoint did not return valid JSON. Text (truncated):")
        print(r2.text[:1000])
        return

    postings = get_posting_list_from_json(postings_json)
    if postings is None:
        print("Could not find a postings list in the response JSON. Top-level keys:", list(postings_json.keys()))
        return

    print(f"Found {len(postings)} postings (limited by request params).")

    stats_by_posting = {}
    for idx, item in enumerate(postings, start=1):
        posting_id = get_posting_id(item)
        if posting_id is None:
            print(f"[{idx}] Could not determine posting id for item: keys={list(item.keys())}")
            continue

        stat_url = STAT_URL_TEMPLATE.format(posting_id=posting_id)
        try:
            r_stat = s.get(stat_url, timeout=15)
            r_stat.raise_for_status()
            try:
                stat_json = r_stat.json()
            except ValueError:
                print(f"[{idx}] Stat endpoint returned non-json for posting {posting_id}. Text truncated:")
                print(r_stat.text[:400])
                stat_json = {"raw_text": r_stat.text[:400]}
            stats_by_posting[posting_id] = stat_json
            print(f"[{idx}] Fetched stats for posting {posting_id}")
        except Exception as e:
            print(f"[{idx}] Failed to fetch stats for posting {posting_id}: {e}")

        time.sleep(REQUEST_DELAY)

    # Example of how to use results: print a compact summary
    print("\nSummary of fetched stats:")
    for pid, sj in stats_by_posting.items():
        # print pid and top-level keys of the stats object
        if isinstance(sj, dict):
            print(f" - {pid}: keys={list(sj.keys())}")
        else:
            print(f" - {pid}: (non-dict response)")

    # Optional: return mapping if script is imported
    return stats_by_posting


if __name__ == "__main__":
    main()
