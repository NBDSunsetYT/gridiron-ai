"""Authorized CollegeFootballData reads through the private Render data bridge.

No API key is read until both bridge authentication and Render provenance pass.
No injuries, depth charts or event-contract prices are synthesized from statistics.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from .sports_data_common import DataProviderError, require_render_runtime, utc_now

CFBD_ORIGIN = "https://api.collegefootballdata.com"
# Verified against the provider's published OpenAPI document, not private endpoints.
CFBD_RESOURCES = {
    "games": {"year", "week", "seasonType", "team", "home", "away", "conference", "id"},
    "teams/fbs": {"year"},
    "conferences": set(),
    "rankings": {"year", "week", "seasonType"},
    "roster": {"year", "team"},
    "stats/season": {"year", "team", "conference", "startWeek", "endWeek"},
    "stats/player/season": {"year", "team", "conference", "startWeek", "endWeek", "seasonType", "category"},
    "plays": {"year", "week", "seasonType", "team", "offense", "defense", "gameId", "playType", "classification"},
    "plays/stats": {"year", "week", "team", "gameId", "athleteId", "statTypeId", "seasonType"},
    "player/usage": {"year", "team", "conference", "position", "playerId", "excludeGarbageTime"},
    "lines": {"year", "week", "seasonType", "team", "home", "away", "conference", "gameId"},
}
_cache: dict[str, tuple[float, dict, int]] = {}
MAX_CACHE_BYTES = 12_000_000
_lock = threading.Lock()
_calls: list[float] = []


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def _query(resource: str, values: list[tuple[str, str]]) -> dict[str, str]:
    if resource not in CFBD_RESOURCES:
        raise DataProviderError("unsupported_resource", "This college-football resource is not supported.", http_status=404)
    result: dict[str, str] = {}
    for key, value in values:
        if key not in CFBD_RESOURCES[resource] or key in result or not value or len(value) > 180:
            raise DataProviderError("invalid_query", "Use documented, bounded college-football query fields.", http_status=400)
        if key in {"year", "week", "startWeek", "endWeek", "gameId", "id", "athleteId", "statTypeId", "playerId", "playType"}:
            if not value.isdecimal() or len(value) > 14:
                raise DataProviderError("invalid_query", "College-football numeric identifiers must be exact positive integers.", http_status=400)
            number = int(value)
            if key == "year" and not 2000 <= number <= datetime.now(timezone.utc).year + 1:
                raise DataProviderError("invalid_query", "Choose a supported college-football season.", http_status=400)
            if key in {"week", "startWeek", "endWeek"} and not 1 <= number <= 30:
                raise DataProviderError("invalid_query", "Choose a supported college-football week.", http_status=400)
        if key == "seasonType" and value not in {"regular", "postseason", "both"}:
            raise DataProviderError("invalid_query", "Choose an available college-football season type.", http_status=400)
        if key == "classification" and value not in {"fbs", "fcs", "ii", "iii"}:
            raise DataProviderError("invalid_query", "Choose a supported college-football classification.", http_status=400)
        if key == "excludeGarbageTime" and value not in {"true", "false"}:
            raise DataProviderError("invalid_query", "A boolean college-football usage option is required.", http_status=400)
        result[key] = value
    if resource not in {"conferences", "roster", "teams/fbs"} and "year" not in result:
        raise DataProviderError("invalid_query", "Select the actual college-football season.", http_status=400)
    return result


def _read(resource: str, params: dict[str, str], key: str) -> dict:
    require_render_runtime()
    url = CFBD_ORIGIN + "/" + resource + ("?" + urllib.parse.urlencode(sorted(params.items())) if params else "")
    now = time.monotonic()
    with _lock:
        stored = _cache.get(url)
        if stored and stored[0] > now:
            return {**stored[1], "cache": "fresh_cached"}
        _calls[:] = [at for at in _calls if at > now - 60]
        if len(_calls) >= 4:
            raise DataProviderError("local_rate_limit", "College-football provider refresh is rate limited. Fresh cached data remains available.", http_status=429, retryable=True, retry_after=60)
        _calls.append(now)
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=25) as response:
            content = response.read(8_000_001)
            if len(content) > 8_000_000:
                raise DataProviderError("response_too_large", "The college-football response exceeds its bounded ingestion limit.", http_status=413)
            value = json.loads(content)
    except urllib.error.HTTPError as error:
        status = error.code
        if status in {401, 403}:
            raise DataProviderError("authorization_or_tier_required", "CollegeFootballData did not authorize this resource. Verify the provider account and subscription permissions.", http_status=status, requires_operator=True) from None
        if status == 429:
            raise DataProviderError("provider_rate_limit", "CollegeFootballData is rate limited. Retry after the provider's window.", http_status=429, retryable=True, retry_after=60) from None
        raise DataProviderError("provider_unavailable", "The authorized college-football resource is temporarily unavailable.", http_status=503, retryable=True) from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        raise DataProviderError("provider_unavailable", "The college-football provider response could not be verified.", http_status=503, retryable=True) from None
    checked = utc_now()
    result = {"sport": "CFB", "provider": "CollegeFootballData", "resource": resource, "data": value, "sourceUrl": url, "checkedAt": checked, "cache": "fresh", "marketFamily": "sportsbook_reference" if resource == "lines" else None, "limitations": ["Provider access is not evidence of calibrated model accuracy.", "Traditional sportsbook lines are not DraftKings Predictions event contracts.", "Injury and depth-chart coverage are not inferred from missing statistics."]}
    size = len(json.dumps(result, separators=(",", ":")).encode("utf-8"))
    with _lock:
        _cache.pop(url, None)
        while _cache and (len(_cache) >= 16 or sum(item[2] for item in _cache.values()) + size > MAX_CACHE_BYTES):
            del _cache[next(iter(_cache))]
        if size <= MAX_CACHE_BYTES:
            _cache[url] = (now + (60 if resource in {"games", "lines"} else 600), result, size)
    return result


def create_cfbd_router(bridge_guard) -> APIRouter:
    router = APIRouter(prefix="/data/cfb", tags=["private college-football data"])

    def authorize(authorization):
        bridge_guard(authorization)
        require_render_runtime()

    @router.get("/status")
    def status(authorization: str | None = Header(default=None)):
        authorize(authorization)
        configured = bool(os.environ.get("CFBD_API_KEY", "").strip())
        return {"sport": "CFB", "provider": "CollegeFootballData", "configured": configured, "status": "configured_unverified" if configured else "credential_missing", "checkedAt": utc_now(), "sourceUrl": "https://collegefootballdata.com", "message": "Resource access is verified only by actual provider responses." if configured else "CollegeFootballData access requires a key configured only on the private Render data service.", "apiKeyExposed": False}

    @router.get("/{resource:path}")
    def resource_data(resource: str, request: Request, authorization: str | None = Header(default=None)):
        authorize(authorization)
        params = _query(resource, list(request.query_params.multi_items()))
        key = os.environ.get("CFBD_API_KEY", "").strip()
        if not key:
            raise DataProviderError("credential_missing", "CollegeFootballData access is not configured on the private data service.", http_status=503, requires_operator=True)
        return _read(resource, params, key)

    return router
