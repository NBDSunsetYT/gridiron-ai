"""Private HTTP boundaries. Synthetic artifacts only; not accuracy evidence."""
import os,tempfile,unittest,urllib.error
from unittest.mock import patch
from fastapi.testclient import TestClient
from modeling.service import app,signature
from modeling.nba_v15 import VERSION
class EngineRouteTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'SIMULATION_SERVICE_TOKEN':'synthetic-boundary-only-not-production-token-15000'});self.env.start();self.client=TestClient(app);self.headers={'Authorization':'Bearer '+os.environ['SIMULATION_SERVICE_TOKEN']}
 def tearDown(self):self.client.close();self.env.stop()
 def model(self,**changes):
  m={'version':VERSION,'sport':'NBA','signatureVersion':'numeric-canonical-v1',**changes};m['signature']=signature(m);return m
 def test_private_paths_reject_guest_access(self):
  self.assertEqual(self.client.get('/v15/status').status_code,401)
  for p in ['/nba/prepare','nba/analyze','/v15/football/analyze']:self.assertEqual(self.client.post(p,json={}).status_code,401)
 def test_signature_and_cross_sport_rejection(self):
  for m in [{},self.model(sport='NFL')]:self.assertEqual(self.client.post('/nba/analyze',headers=self.headers,json={'model':m}).status_code,422)
  m=self.model();m['sport']='NFL';self.assertEqual(self.client.post('/nba/analyze',headers=self.headers,json={'model':m}).status_code,422)
 def test_current_preparation_rejects_arbitrary_historical_cutoff(self):
  self.assertEqual(self.client.post('/nba/prepare',headers=self.headers,json={'cutoff':'2020-01-01T00:00:00Z'}).status_code,422)
 def test_source_outage_is_retryable_service_error_not_fake_evidence(self):
  with tempfile.TemporaryDirectory() as folder,patch('modeling.engine_v15_routes.tempfile.gettempdir',return_value=folder),patch('modeling.engine_v15_routes.urllib.request.urlopen',side_effect=urllib.error.URLError('synthetic source failure')):
   response=self.client.post('/nba/prepare',headers=self.headers,json={})
  self.assertEqual(response.status_code,503);self.assertIn('could not be retrieved',response.json()['detail'])
 def test_nonstandard_counts_never_enter_inference(self):
  with patch('modeling.nba_v15.simulate_nba') as infer:
   for n in [True,9999,200000]:self.assertEqual(self.client.post('/nba/analyze',headers=self.headers,json={'model':self.model(),'simulations':n}).status_code,422)
   infer.assert_not_called()
 def test_synthetic_fixture_cannot_become_deployed_forecast(self):
  with patch.dict(os.environ,{'VERCEL':'1'}),patch('modeling.nba_v15.simulate_nba') as infer:
   response=self.client.post('/nba/analyze',headers=self.headers,json={'model':self.model(syntheticEvidence=True),'simulations':10000})
   self.assertEqual(response.status_code,422);infer.assert_not_called()
