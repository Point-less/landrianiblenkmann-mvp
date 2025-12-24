"""Tokkobroker API integration utilities."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class TokkoIntegrationError(Exception):
    """Base exception for Tokkobroker integration failures."""


class TokkoAuthenticationError(TokkoIntegrationError):
    """Raised when Tokkobroker authentication fails."""


@dataclass
class TokkoExtractionResult:
    """Container for extracted Tokkobroker data."""

    properties: List[Dict[str, Any]]
    unmatched_reservations: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class TokkoClient:
    """Thin wrapper over requests.Session for Tokkobroker."""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (TokkoExtractor)",
                "Accept": "application/json",
            }
        )

    def _get_csrf_token(self, html: str) -> str | None:
        match = re.search(r"name='csrfmiddlewaretoken' value='([^']+)'", html)
        return match.group(1) if match else None

    def _prepare_request_url(self, url: str, params: Mapping[str, Any] | None) -> str:
        prepared = requests.Request("GET", url, params=params).prepare()
        return prepared.url

    def _api_get(self, endpoint: str, params: Mapping[str, Any] | None = None) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        headers = {"X-Requested-With": "XMLHttpRequest"}
        request_url = self._prepare_request_url(url, params)
        logger.debug("Tokkobroker GET %s headers=%s", request_url, headers)
        try:
            response = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            logger.exception("Tokkobroker GET %s failed", request_url)
            raise TokkoIntegrationError(f"Tokkobroker GET {endpoint} failed") from exc
        logger.debug(
            "Tokkobroker GET %s completed status=%s content_length=%s",
            response.request.url if response.request else request_url,
            response.status_code,
            response.headers.get("Content-Length"),
        )
        return response

    def call_property_endpoint(
        self,
        property_id: int,
        params: Mapping[str, Any],
        *,
        action: str,
    ) -> requests.Response:
        """Perform a property endpoint request with detailed logging."""

        url = f"{self.base_url}/property/{property_id}/"
        logger.debug(
            "Tokkobroker property request action=%s property=%s params=%s url=%s",
            action,
            property_id,
            params,
            self._prepare_request_url(url, params),
        )
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            logger.exception(
                "Tokkobroker property request action=%s property=%s failed",
                action,
                property_id,
            )
            raise TokkoIntegrationError(
                f"Tokkobroker property request failed ({action})"
            ) from exc

        logger.debug(
            "Tokkobroker property request action=%s property=%s status=%s content_length=%s url=%s",
            action,
            property_id,
            response.status_code,
            response.headers.get("Content-Length"),
            response.request.url if response.request else url,
        )
        return response

    def authenticate(self, username: str, password: str, token: str | None = None) -> None:
        login_page_url = f"{self.base_url}/go/"
        try:
            logger.debug("Requesting Tokkobroker login page %s", login_page_url)
            response = self.session.get(login_page_url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise TokkoAuthenticationError("unable to reach login page") from exc
        logger.debug("Tokkobroker login page status=%s", response.status_code)
        if response.status_code != 200:
            raise TokkoAuthenticationError(f"login page returned {response.status_code}")

        csrf_token = self._get_csrf_token(response.text)
        if not csrf_token:
            raise TokkoAuthenticationError("CSRF token missing from login page")
        logger.debug("Tokkobroker login CSRF token extracted for user %s", username)

        login_url = f"{self.base_url}/login/?next=/home"
        form_data = {
            "username": username,
            "password": password,
            "csrfmiddlewaretoken": csrf_token,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": login_page_url,
            "Origin": self.base_url,
        }
        try:
            logger.debug("Submitting Tokkobroker credentials for user %s", username)
            response = self.session.post(
                login_url,
                data=form_data,
                headers=headers,
                allow_redirects=True,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TokkoAuthenticationError("credential submission failed") from exc
        logger.debug(
            "Tokkobroker login submission response status=%s redirect_url=%s",
            response.status_code,
            response.url,
        )

        if "jopi/user_token_validation" in response.url:
            logger.info("Tokkobroker admin user detected; performing OTP validation")
            csrf_token_otp = self._get_csrf_token(response.text)
            if not csrf_token_otp:
                raise TokkoAuthenticationError("OTP CSRF token missing")
            logger.debug("Tokkobroker OTP CSRF token extracted for user %s", username)

            otp_url = f"{self.base_url}/jopi/user_token_validation/1?next=/home"
            otp_data = {
                "token": token or "123456",
                "csrfmiddlewaretoken": csrf_token_otp,
            }
            try:
                logger.debug("Submitting Tokkobroker OTP for user %s", username)
                response = self.session.post(
                    otp_url,
                    data=otp_data,
                    headers=headers,
                    allow_redirects=True,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                raise TokkoAuthenticationError("OTP submission failed") from exc
            logger.debug(
                "Tokkobroker OTP submission response status=%s redirect_url=%s",
                response.status_code,
                response.url,
            )
            if "/jopi" not in response.url:
                raise TokkoAuthenticationError("OTP validation failed")
        elif "/home" not in response.url:
            raise TokkoAuthenticationError("Unexpected redirect during login")

        logger.info("Tokkobroker authentication successful")


class TokkoPropertiesExtractor:
    """High-level data extractor based on the standalone script provided."""

    def __init__(self, client: TokkoClient, objects_per_page: int = 1000):
        self.client = client
        self.objects_per_page = objects_per_page

    def extract_all_data(self) -> TokkoExtractionResult:
        logger.info("Tokkobroker extraction started (page_size=%s)", self.objects_per_page)
        properties = self._fetch_properties()
        if properties:
            self._enrich_properties(properties)

        branch_ids = self._fetch_branch_ids()
        property_type_ids = self._fetch_property_type_ids()
        reservations = self._fetch_reservations(branch_ids, property_type_ids)

        logger.info(
            "Tokkobroker metadata fetched (branches=%s property_types=%s reservations=%s)",
            len(branch_ids),
            len(property_type_ids),
            len(reservations),
        )

        unmatched_reservations = self._assign_reservations(properties, reservations)
        metadata = {
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "branch_ids": branch_ids,
            "property_type_ids": property_type_ids,
            "reservation_count": len(reservations),
        }
        return TokkoExtractionResult(properties=properties, unmatched_reservations=unmatched_reservations, metadata=metadata)

    def _fetch_properties(self) -> List[Dict[str, Any]]:
        properties: List[Dict[str, Any]] = []
        page = 1
        while True:
            logger.info("Requesting Tokkobroker properties page %s", page)
            response = self.client._api_get(
                "/api3/property",
                params={"page": page, "objects_per_page": self.objects_per_page},
            )
            if response.status_code != 200:
                logger.warning("Tokkobroker property request failed (page %s): %s", page, response.status_code)
                break
            try:
                data = response.json()
            except json.JSONDecodeError as exc:
                logger.error("Tokkobroker property response is not JSON (page %s): %s", page, exc)
                break

            page_properties, has_next = self._parse_paginated_collection(data)
            if not page_properties:
                logger.info("Tokkobroker property page %s empty; stopping", page)
                break

            first_id = page_properties[0].get("id") if page_properties else None
            last_id = page_properties[-1].get("id") if page_properties else None
            logger.info(
                "Tokkobroker page %s returned %s properties (ids %s-%s, has_next=%s)",
                page,
                len(page_properties),
                first_id,
                last_id,
                has_next,
            )

            properties.extend(page_properties)
            if not has_next:
                break
            page += 1

        logger.info("Fetched %s Tokkobroker properties across %s page(s)", len(properties), page)
        return properties

    def _enrich_properties(self, properties: Iterable[MutableMapping[str, Any]]) -> None:
        for prop in properties:
            property_id = prop.get("id")
            if not property_id:
                continue
            prop["image_files"] = self._safe_json(self.client._api_get("/api3/property/files", params={"properties": property_id, "file_type": "image"}))
            prop["files"] = self._safe_json(self.client._api_get("/api3/property/files", params={"properties": property_id, "file_type": "files"}))
            prop["quick_data"] = self._safe_json(self.client._api_get(f"/api3/property/{property_id}/quick"))
            prop["quick_sents"] = self._safe_json(self.client._api_get(f"/api3/property/{property_id}/quick/sents"))

    def _fetch_branch_ids(self) -> List[str]:
        response = self.client._api_get("/api3/company/branch")
        return self._extract_ids(response, fallback_label="branch")

    def _fetch_property_type_ids(self) -> List[str]:
        response = self.client._api_get("/api3/properties/types")
        return self._extract_ids(response, fallback_label="property type")

    def _fetch_reservations(self, branch_ids: Sequence[str], property_type_ids: Sequence[str]) -> List[Dict[str, Any]]:
        fixed_params = {
            "op_type": "[\"1\",\"2\",\"3\"]",
            "reservation_status": "[\"A\",\"C\",\"F\"]",
            "res_prop_agents": "[\"-1\"]",
            "res_prop_managers": "[\"-1\"]",
            "est_from": "",
            "est_to": "",
            "last_mod_date": "",
        }
        branches_param = "[\"-1\"" + ("," + ",".join(f'\"{bid}\"' for bid in branch_ids) if branch_ids else "") + "]"
        types_param = "[" + ",".join(f'\"{tid}\"' for tid in property_type_ids) + "]" if property_type_ids else "[]"
        params = {**fixed_params, "branches_list_select": branches_param, "res_prop_type": types_param}

        response = self.client._api_get("/properties/filter_reservations", params=params)
        if response.status_code != 200:
            logger.warning("Tokkobroker reservation request failed: %s", response.status_code)
            return []
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            logger.error("Reservation response is not JSON: %s", exc)
            return []

        if isinstance(data, list):
            logger.info("Tokkobroker reservations payload returned %s entries", len(data))
            return data
        if isinstance(data, dict):
            for field in ["reservations", "results", "data", "objects", "aaData"]:
                if field in data and isinstance(data[field], list):
                    logger.info(
                        "Tokkobroker reservations payload returned %s entries via '%s'",
                        len(data[field]),
                        field,
                    )
                    return data[field]
            return [data]
        return []

    def _assign_reservations(self, properties: Iterable[MutableMapping[str, Any]], reservations: Iterable[Mapping[str, Any]] | None) -> List[Dict[str, Any]]:
        reservations_by_property: Dict[Any, List[Dict[str, Any]]] = {}
        unmatched: List[Dict[str, Any]] = []
        for reservation in reservations or []:
            property_id = reservation.get("id")
            if property_id is None:
                unmatched.append(dict(reservation))
                continue
            reservations_by_property.setdefault(property_id, []).append(reservation)

        for prop in properties:
            property_id = prop.get("id")
            prop["reservations"] = reservations_by_property.get(property_id, [])

        logger.info("Assigned reservations to %s properties; unmatched=%s", len(reservations_by_property), len(unmatched))
        return unmatched

    def _safe_json(self, response: requests.Response | None) -> Any:
        if not response or response.status_code != 200:
            return None
        try:
            return response.json()
        except json.JSONDecodeError:
            return None

    def _parse_paginated_collection(self, payload: Any) -> tuple[List[Dict[str, Any]], bool]:
        properties: List[Dict[str, Any]] = []
        has_next = False
        if isinstance(payload, list):
            properties = payload
        elif isinstance(payload, dict):
            for field in ["properties", "results", "data", "objects"]:
                if field in payload and isinstance(payload[field], list):
                    properties = payload[field]
                    break
            page_info = payload.get("page_info") or payload.get("pagination") or payload.get("meta")
            if isinstance(page_info, Mapping):
                if "has_next" in page_info:
                    has_next = bool(page_info["has_next"])
                elif "num_pages" in page_info and "page" in page_info:
                    try:
                        has_next = int(page_info["page"]) < int(page_info["num_pages"])
                    except (ValueError, TypeError):
                        has_next = False
        return properties, has_next

    def _extract_ids(self, response: requests.Response, fallback_label: str) -> List[str]:
        if response.status_code != 200:
            logger.warning("Tokkobroker %s request failed: %s", fallback_label, response.status_code)
            return []
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            logger.error("%s response not JSON: %s", fallback_label.title(), exc)
            return []

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for field in ["branches", "property_type", "types", "results", "data", "objects"]:
                if field in data and isinstance(data[field], list):
                    items = data[field]
                    break
            else:
                items = [data]
        else:
            items = []

        ids: List[str] = []
        for item in items:
            if isinstance(item, Mapping) and "id" in item:
                ids.append(str(item["id"]))
        logger.info("Tokkobroker %s ids extracted: %s", fallback_label, len(ids))
        return ids


def fetch_tokkobroker_properties() -> List[Dict[str, Any]]:
    """Fetch Tokkobroker properties using credentials from settings."""

    base_url = settings.TOKKO_BASE_URL
    username = settings.TOKKO_USERNAME
    password = settings.TOKKO_PASSWORD
    otp_token = settings.TOKKO_OTP_TOKEN
    timeout = settings.TOKKO_TIMEOUT

    client = TokkoClient(base_url=base_url, timeout=timeout)
    try:
        client.authenticate(username=username, password=password, token=otp_token)
    except TokkoAuthenticationError:
        logger.exception("Tokkobroker authentication failed")
        return []

    extractor = TokkoPropertiesExtractor(client)
    try:
        result = extractor.extract_all_data()
    except TokkoIntegrationError:
        logger.exception("Tokkobroker extraction failed")
        return []

    logger.info(
        "Tokkobroker extractor finished: properties=%s unmatched_reservations=%s",
        len(result.properties),
        len(result.unmatched_reservations),
    )
    return result.properties


__all__ = ["fetch_tokkobroker_properties", "TokkoClient", "TokkoPropertiesExtractor", "TokkoExtractionResult"]
