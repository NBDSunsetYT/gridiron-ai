"""Synthetic credentials only; rotation must not invalidate legacy callers."""
import os,unittest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from .sports_data_common import authorize_data_bridge
from .sports_data_gateway import app

class RotationTests(unittest.TestCase):
    OLD='SYNTHETIC-legacy-token-abcdefghijklmnopqrstuvwxyz'
    NEW='SYNTHETIC-staging-token-abcdefghijklmnopqrstuvwxyz'
    def test_overlap_accepts_both_and_rejects_unknown_without_disclosure(self):
        with patch.dict(os.environ,{'GRIDIRON_DATA_BRIDGE_TOKEN':self.OLD,'GRIDIRON_DATA_BRIDGE_STAGING_TOKEN':self.NEW}):
            authorize_data_bridge('Bearer '+self.OLD);authorize_data_bridge('Bearer '+self.NEW)
            for value in [None,'Bearer wrong','bearer '+self.NEW,self.NEW]:
                with self.assertRaises(HTTPException) as e:authorize_data_bridge(value)
                self.assertEqual(e.exception.status_code,401)
                self.assertNotIn(self.OLD,str(e.exception.detail));self.assertNotIn(self.NEW,str(e.exception.detail))
    def test_short_staging_key_is_not_accepted_and_legacy_remains_valid(self):
        with patch.dict(os.environ,{'GRIDIRON_DATA_BRIDGE_TOKEN':self.OLD,'GRIDIRON_DATA_BRIDGE_STAGING_TOKEN':'short'}):
            authorize_data_bridge('Bearer '+self.OLD)
            with self.assertRaises(HTTPException):authorize_data_bridge('Bearer short')
    def test_missing_primary_fails_closed(self):
        with patch.dict(os.environ,{'GRIDIRON_DATA_BRIDGE_TOKEN':'','GRIDIRON_DATA_BRIDGE_STAGING_TOKEN':self.NEW}):
            with self.assertRaises(HTTPException) as e:authorize_data_bridge('Bearer '+self.NEW)
            self.assertEqual(e.exception.status_code,503)
    def test_retiring_staging_does_not_rotate_primary(self):
        with patch.dict(os.environ,{'GRIDIRON_DATA_BRIDGE_TOKEN':self.OLD,'GRIDIRON_DATA_BRIDGE_STAGING_TOKEN':''}):
            authorize_data_bridge('Bearer '+self.OLD)
            with self.assertRaises(HTTPException):authorize_data_bridge('Bearer '+self.NEW)
    def test_real_gateway_metrics_accepts_both_without_provider_calls(self):
        with patch.dict(os.environ,{'GRIDIRON_DATA_BRIDGE_TOKEN':self.OLD,'GRIDIRON_DATA_BRIDGE_STAGING_TOKEN':self.NEW}),TestClient(app) as client:
            for token in [self.OLD,self.NEW]:
                r=client.get('/metrics',headers={'Authorization':'Bearer '+token});self.assertEqual(r.status_code,200)
                self.assertNotIn(self.OLD,r.text);self.assertNotIn(self.NEW,r.text)
