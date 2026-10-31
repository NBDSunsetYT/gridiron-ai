"""SYNTHETIC source/HTTP failures; never fabricates research after an outage."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from fastapi.testclient import TestClient
from .public_research import ResearchUnavailable,analyze_public,fetch_dataset,source_url,stamp
from .service import app
from .test_public_research import GAME,NOW


def http_error(code):
    return urllib.error.HTTPError(source_url('pbp',2026),code,'SYNTHETIC upstream status',{},None)


class PublicSourceRetryTests(unittest.TestCase):
    def test_source_429_and_5xx_are_retryable_but_missing_source_is_not(self):
        for code in (408,429,500,503,504,403,404):
            with self.subTest(code=code),tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'GRIDIRON_PUBLIC_CACHE_DIR':directory}),patch('modeling.public_research.urllib.request.urlopen',side_effect=http_error(code)):
                with self.assertRaises(ResearchUnavailable) as caught:fetch_dataset('pbp',2026)
                retryable=code in (408,429) or code>=500
                self.assertEqual(caught.exception.retryable,retryable)
                self.assertEqual(caught.exception.status_code,503 if retryable else 422)
                self.assertEqual(caught.exception.upstream_status_code,code)

    def test_network_os_errors_and_timeouts_are_retryable(self):
        for error in (TimeoutError('SYNTHETIC timeout'),urllib.error.URLError('SYNTHETIC network unavailable'),OSError('SYNTHETIC connection failure')):
            with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'GRIDIRON_PUBLIC_CACHE_DIR':directory}),patch('modeling.public_research.urllib.request.urlopen',side_effect=error):
                with self.assertRaises(ResearchUnavailable) as caught:fetch_dataset('pbp',2026)
                self.assertTrue(caught.exception.retryable);self.assertEqual(caught.exception.status_code,503)

    def test_incompatible_source_schema_remains_nonretryable(self):
        class Response(io.BytesIO):
            headers={}
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'GRIDIRON_PUBLIC_CACHE_DIR':directory}),patch('modeling.public_research.urllib.request.urlopen',return_value=Response(gzip.compress(b'unrelated,columns\nSYNTHETIC,DATA\n'))):
            with self.assertRaisesRegex(ResearchUnavailable,'schema changed') as caught:fetch_dataset('pbp',2026)
            self.assertFalse(caught.exception.retryable);self.assertEqual(caught.exception.status_code,422)

    def test_failed_head_and_get_never_publish_old_cached_bytes_as_current(self):
        url=source_url('rosters',2026);key=hashlib.sha256(url.encode()).hexdigest()
        content=gzip.compress(b'team,week,gsis_id,pfr_id,status,full_name\nBUF,8,SYNTH-CACHED,cached,ACT,SYNTHETIC Cached\n')
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'GRIDIRON_PUBLIC_CACHE_DIR':directory}):
            root=Path(directory);asset=root/(key+'.csv.gz');manifest=root/(key+'.json')
            asset.write_bytes(content);metadata=json.dumps({'schemaVerified':True,'checkedAt':stamp(),'etag':'SYNTH-CACHED'})
            manifest.write_text(metadata)
            with patch('modeling.public_research.urllib.request.urlopen',side_effect=[http_error(503),http_error(503)]) as upstream:
                with self.assertRaises(ResearchUnavailable) as caught:fetch_dataset('rosters',2026)
                self.assertTrue(caught.exception.retryable);self.assertEqual(upstream.call_count,2)
                self.assertEqual(upstream.call_args_list[0].args[0].get_method(),'HEAD');self.assertEqual(upstream.call_args_list[1].args[0].get_method(),'GET')
            self.assertEqual(asset.read_bytes(),content);self.assertEqual(manifest.read_text(),metadata)

    def test_pipeline_preserves_retryability_instead_of_completing_a_partial_cache(self):
        class Source:
            metadata={'status':'available','url':'https://example.invalid/SYNTHETIC-source'}
        for failing in ('pbp','injuries'):
            def fetcher(kind,_season):
                if kind==failing:raise ResearchUnavailable('SYNTHETIC temporary source failure',retryable=True,upstream_status_code=503)
                return Source()
            with self.subTest(failing=failing),patch('modeling.public_research.fit_csv') as fit:
                with self.assertRaises(ResearchUnavailable) as caught:analyze_public({'game':GAME},fetcher=fetcher,now=NOW)
                self.assertEqual(caught.exception.status_code,503);self.assertTrue(caught.exception.retryable);fit.assert_not_called()

    def test_private_endpoint_keeps_auth_and_distinguishes_transient_from_evidence_errors(self):
        token='SYNTHETIC-PRIVATE-RETRY-SERVICE-KEY-0123456789'
        with patch.dict(os.environ,{'SIMULATION_SERVICE_TOKEN':token}),TestClient(app) as client:
            with patch('modeling.public_research.analyze_public') as compute:
                self.assertEqual(client.post('/public/analyze',json={'game':GAME}).status_code,401);compute.assert_not_called()
            headers={'Authorization':'Bearer '+token}
            for status in (429,503):
                with patch('modeling.public_research.analyze_public',side_effect=ResearchUnavailable('SYNTHETIC sensitive provider exception',retryable=True,upstream_status_code=status)):
                    response=client.post('/public/analyze',json={'game':GAME},headers=headers)
                    self.assertEqual(response.status_code,503);self.assertEqual(response.headers['Retry-After'],'15');self.assertEqual(response.headers['X-Gridiron-Retryable'],'true')
                    self.assertNotIn('sensitive provider exception',response.text)
            with patch('modeling.public_research.analyze_public',side_effect=ResearchUnavailable('SYNTHETIC insufficient historical cohort')):
                response=client.post('/public/analyze',json={'game':GAME},headers=headers)
                self.assertEqual(response.status_code,422);self.assertEqual(response.headers['X-Gridiron-Retryable'],'false');self.assertIn('insufficient historical cohort',response.text)
            with patch('modeling.public_research.analyze_public',return_value={'result':{'simulations':10000},'requiresDatasetUpload':False}):
                self.assertEqual(client.post('/public/analyze',json={'game':GAME},headers=headers).status_code,200)


if __name__=='__main__':unittest.main()
