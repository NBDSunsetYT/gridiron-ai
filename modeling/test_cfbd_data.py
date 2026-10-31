"""Isolated gateway fixtures. Never contacts a provider or uses a real key."""
import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from . import cfbd_data as module
from .sports_data_common import DataProviderError, authorize_data_bridge


class CollegeDataGatewayTests(unittest.TestCase):
    def setUp(self):
        module._cache.clear()
        module._calls.clear()
        self.token = "SYNTHETIC-CFB-BRIDGE-TOKEN-ONLY-FOR-UNIT-TESTS"
        self.key = "SYNTHETIC-CFBD-KEY-ONLY-FOR-UNIT-TESTS"
        self.environment = {"RENDER": "true", "RENDER_SERVICE_ID": "SYNTHETIC-SERVICE", "GRIDIRON_DATA_BRIDGE_TOKEN": self.token}
        self.app = FastAPI()
        self.app.include_router(module.create_cfbd_router(authorize_data_bridge))

        @self.app.exception_handler(DataProviderError)
        async def failed(request, error):
            return JSONResponse({"sport": "CFB", "error": error.diagnostic()}, status_code=error.http_status or 503)

        self.client = TestClient(self.app)
        self.headers = {"Authorization": "Bearer " + self.token}

    def test_bridge_and_render_guard_precede_provider_key_read(self):
        class NoKeyRead(dict):
            def get(self, name, default=None):
                if name == "CFBD_API_KEY":
                    raise AssertionError("Provider key read outside the authorized Render boundary")
                return super().get(name, default)
        environment = NoKeyRead({**self.environment, "RENDER": ""})
        with patch.object(os, "environ", environment):
            self.assertEqual(self.client.get("/data/cfb/status").status_code, 401)
            response = self.client.get("/data/cfb/status", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "render_backend_required")

    def test_missing_key_is_not_a_live_data_claim(self):
        with patch.dict(os.environ, self.environment, clear=True):
            response = self.client.get("/data/cfb/status", headers=self.headers)
            games = self.client.get("/data/cfb/games?year=2026", headers=self.headers)
        self.assertFalse(response.json()["configured"])
        self.assertEqual(games.status_code, 503)
        self.assertEqual(games.json()["error"]["code"], "credential_missing")

    def test_only_documented_bounded_resources_can_be_requested(self):
        with patch.dict(os.environ, {**self.environment, "CFBD_API_KEY": self.key}, clear=True), patch.object(module.urllib.request, "build_opener") as opener:
            for route in ["injuries?year=2026", "games?year=2026&url=https://unrelated.invalid", "games?year=2026&year=2025", "games?year=2026&week=99"]:
                self.assertIn(self.client.get("/data/cfb/" + route, headers=self.headers).status_code, (400, 404))
            opener.assert_not_called()

    def test_authorized_response_retains_exact_source_and_no_secret(self):
        raw = json.dumps([{"id": 123, "homeTeam": "SYNTHETIC TEAM"}]).encode()
        with patch.dict(os.environ, {**self.environment, "CFBD_API_KEY": self.key}, clear=True), patch.object(module.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(raw)
            response = self.client.get("/data/cfb/games?year=2026&week=10", headers=self.headers)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer " + self.key)
            self.assertTrue(request.full_url.startswith(module.CFBD_ORIGIN + "/games?"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["id"], 123)
        self.assertNotIn(self.key, response.text)
        self.assertEqual(response.json()["sport"], "CFB")

    def test_provider_forbidden_is_preserved_without_an_odds_fallback(self):
        with patch.dict(os.environ, {**self.environment, "CFBD_API_KEY": self.key}, clear=True), patch.object(module.urllib.request, "build_opener") as opener:
            opener.return_value.open.side_effect = urllib.error.HTTPError(module.CFBD_ORIGIN, 403, "Forbidden", {}, None)
            response = self.client.get("/data/cfb/lines?year=2026", headers=self.headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "authorization_or_tier_required")
        self.assertNotIn("data", response.json())

    def test_total_cache_is_bounded_across_distinct_provider_resources(self):
        raw = json.dumps([{"note": "SYNTHETIC" * 225000}]).encode()
        with patch.dict(os.environ, {**self.environment, "CFBD_API_KEY": self.key}, clear=True), patch.object(module.urllib.request, "build_opener") as opener:
            for week in range(1, 9):
                module._calls.clear()
                opener.return_value.open.return_value = io.BytesIO(raw)
                self.assertEqual(self.client.get("/data/cfb/games?year=2026&week=" + str(week), headers=self.headers).status_code, 200)
                self.assertLessEqual(sum(value[2] for value in module._cache.values()), module.MAX_CACHE_BYTES)
        self.assertLess(len(module._cache), 8)


if __name__ == "__main__":
    unittest.main()
