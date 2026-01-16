#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zonaprop client to authenticate and fetch postings + statistics.

Example usage:
    client = ZonapropClient(email="...", password="...")
    client.login()
    postings_response = client.fetch_postings()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Type, TypeVar

import requests
from pydantic import BaseModel, Field

BASE = "https://www.zonaprop.com.ar"
PRE_LOGIN_URL = f"{BASE}/rp-api/user/{{email}}"
LOGIN_URL = f"{BASE}/login_login.ajax"
GET_SESSION = f"{BASE}/rp-api/user/session"
POSTINGS_URL = f"{BASE}/avisos-api/panel/api/v2/postings"
STAT_URL_TEMPLATE = f"{BASE}/avisos-api/panel/api/v1/statistic/posting/{{posting_id}}"
STAT_DAILY_URL_TEMPLATE = (
    f"{BASE}/avisos-api/panel/api/v1/statistic/posting/daily/{{posting_id}}"
)


DEFAULT_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.zonaprop.com.ar/",
    "Origin": "https://www.zonaprop.com.ar",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/139.0.7258.138 Safari/537.36"
    ),
}


class _BaseModel(BaseModel):
    model_config = {"extra": "allow", "populate_by_name": True}


class PostingItem(_BaseModel):
    postingId: int


class PostingsResponse(_BaseModel):
    postings: List[PostingItem]
    numberOfPostings: int


class SummaryMetric(_BaseModel):
    total: int
    percentage: Optional[float] = None
    status: Optional[str] = None


class SummaryStats(_BaseModel):
    impression: SummaryMetric
    visit: SummaryMetric
    leads: SummaryMetric
    user_stat: SummaryMetric = Field(alias="user-stat")
    anonymous_stat: SummaryMetric = Field(alias="anonymous-stat")
    impression_views_conversion: float = Field(alias="impression-views-conversion")
    views_leads_conversion: float = Field(alias="views-leads-conversion")
    userStats: Dict[str, int]


class DailyUserStat(_BaseModel):
    leadForm: int
    socialAds: int
    total: int
    viewData: int
    whatsapp: int
    totalAnonymous: int


class DailyStats(_BaseModel):
    impressions: Dict[str, int]
    views: Dict[str, int]
    leads: Dict[str, int]
    userStat: Dict[str, DailyUserStat]


ModelT = TypeVar("ModelT", bound=_BaseModel)


def _validate_model(model_cls: Type[ModelT], payload: Dict[str, Any]) -> ModelT:
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(payload)  # type: ignore[return-value]
    return model_cls.parse_obj(payload)


def _iter_month_ranges(start_date: date, end_date: date) -> List[tuple[date, date]]:
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


def _merge_daily_stats(
    aggregated: Dict[str, Any],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    for key, value in payload.items():
        if isinstance(value, dict):
            aggregated.setdefault(key, {}).update(value)
        else:
            aggregated[key] = value
    return aggregated


@dataclass
class ZonapropClient:
    email: str
    password: str
    request_delay: float = 0.15
    logger: logging.Logger = logging.getLogger(__name__)
    session: Optional[requests.Session] = None

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def login(self) -> None:
        self._prime_session()
        self._pre_login()
        self._login()
        self._get_session()

    def fetch_postings(
        self,
        *,
        page: int = 1,
        limit: int = 1000,
        search_parameters: str = "status:ONLINE;sort:createdNewer",
        online_first: bool = True,
    ) -> Dict[str, Any]:
        params = {
            "page": page,
            "limit": limit,
            "searchParameters": search_parameters,
            "onlineFirst": str(online_first).lower(),
        }
        headers = {"x-panel-portal": "ZPAR"}
        response = self.session.get(
            POSTINGS_URL, params=params, timeout=15, headers=headers
        )
        self._raise_for_status("Postings", response)
        postings_json = self._parse_json("Postings", response)
        postings_response = _validate_model(PostingsResponse, postings_json)
        max_page = (postings_response.numberOfPostings + limit - 1) // limit
        response_payload = postings_response.model_dump(by_alias=True)
        response_payload["count"] = response_payload.pop("numberOfPostings")
        response_payload["minPage"] = 1
        response_payload["currentPage"] = page
        response_payload["maxPage"] = max_page
        return response_payload

    def fetch_posting_summary(
        self,
        posting_id: int,
        *,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        self._ensure_date_range(start_date, end_date)
        params = {
            "days": 0,
            "startPeriod": start_date.strftime("%Y-%m-%d"),
            "endPeriod": end_date.strftime("%Y-%m-%d"),
        }
        headers = {"x-panel-portal": "ZPAR"}
        url = STAT_URL_TEMPLATE.format(posting_id=posting_id)
        response = self.session.get(url, timeout=15, headers=headers, params=params)
        self._raise_for_status(f"SummaryStats[{posting_id}]", response)
        payload = self._parse_json(f"SummaryStats[{posting_id}]", response)
        return _validate_model(SummaryStats, payload).model_dump(by_alias=True)

    def fetch_posting_daily_stats(
        self,
        posting_id: int,
        *,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        self._ensure_date_range(start_date, end_date)
        headers = {"x-panel-portal": "ZPAR"}
        url = STAT_DAILY_URL_TEMPLATE.format(posting_id=posting_id)
        aggregated: Dict[str, Any] = {}
        for range_start, range_end in _iter_month_ranges(start_date, end_date):
            params = {
                "days": 0,
                "startPeriod": range_start.strftime("%Y-%m-%d"),
                "endPeriod": range_end.strftime("%Y-%m-%d"),
            }
            response = self.session.get(url, timeout=15, headers=headers, params=params)
            self._raise_for_status(
                f"DailyStats[{posting_id}]({params['startPeriod']}..{params['endPeriod']})",
                response,
            )
            payload = self._parse_json("DailyStats", response)
            payload.pop("period", None)
            aggregated = _merge_daily_stats(aggregated, payload)
            time.sleep(self.request_delay)
        return _validate_model(DailyStats, aggregated).model_dump(by_alias=True)

    def _prime_session(self) -> None:
        try:
            response = self.session.get(BASE, timeout=10)
            self._raise_for_status("Prime", response)
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to prime session: {exc}") from exc

    def _pre_login(self) -> None:
        data = {"username": self.email, "origin": "Botón Ingresar"}
        try:
            response = self.session.post(
                PRE_LOGIN_URL.format(email=self.email), timeout=10, json=data
            )
            self._raise_for_status("Pre-login", response)
        except requests.RequestException as exc:
            raise RuntimeError(f"Pre-login failed: {exc}") from exc

    def _login(self) -> None:
        payload = {
            "email": self.email,
            "password": self.password,
            "recordarme": "true",
            "homeSeeker": "true",
            "urlActual": "https://www.zonaprop.com.ar",
        }
        try:
            response = self.session.post(LOGIN_URL, data=payload, timeout=15)
            self._raise_for_status("Login", response)
        except requests.RequestException as exc:
            raise RuntimeError(f"Login failed: {exc}") from exc

        session_cookie = self.session.cookies.get("sessionId")
        if session_cookie:
            self.session.headers["sessionId"] = session_cookie

    def _get_session(self) -> None:
        try:
            response = self.session.get(GET_SESSION, timeout=15)
            self._raise_for_status("Get session", response)
        except requests.RequestException as exc:
            raise RuntimeError(f"Get session failed: {exc}") from exc

    def _parse_json(self, label: str, response: requests.Response) -> Dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"{label} response was not valid JSON: {response.text[:1000]}"
            ) from exc

    def _raise_for_status(self, label: str, response: requests.Response) -> None:
        if response.ok:
            return
        message = (
            f"{label} failed with status {response.status_code}: "
            f"{response.text[:1000]}"
        )
        raise RuntimeError(message)

    def _ensure_date_range(self, start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")



