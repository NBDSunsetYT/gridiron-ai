"""Private CFB route tests with explicitly synthetic, isolated evidence."""
import copy
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from .service import app
from .test_cfb_simulator import cfb_fixture_csv


class CFBServiceTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'SIMULATION_SERVICE_TOKEN':'SYNTHETIC-CFB-SERVICE-ONLY-not-a-real-key-8000',
                                       'GRIDIRON_CFB_TEST_MODE':'1','VERCEL':'','RENDER':''})
        self.env.start();self.client=TestClient(app)
        self.headers={'Authorization':'Bearer '+os.environ['SIMULATION_SERVICE_TOKEN']}

    def tearDown(self):
        self.client.close();self.env.stop()

    def fitted(self):
        response=self.client.post('/cfb/fit',headers=self.headers,json={
            'csv':cfb_fixture_csv(),'source':'SYNTHETIC CFB HTTP mechanical test only','asOf':'2024-02-01T00:00:00Z'})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['model']

    def test_all_cfb_routes_require_private_service_identity(self):
        self.assertEqual(self.client.get('/cfb/status').status_code,401)
        for endpoint in ('/cfb/fit','/cfb/simulate','/cfb/analyze','/cfb/public/analyze','/cfb/public/prepare'):
            self.assertEqual(self.client.post(endpoint,json={}).status_code,401)

    def test_status_does_not_claim_installed_engine_is_a_trained_model(self):
        response=self.client.get('/cfb/status',headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json()['trainedModelAvailable'])
        self.assertTrue(response.json()['requiresFittedCFBEvidence'])
        self.assertEqual(response.json()['supportedSimulationCounts'],[10000,50000,100000])

    def test_missing_play_evidence_withholds_forecasts(self):
        response=self.client.post('/cfb/analyze',headers=self.headers,json={'home':'cfb:A','away':'cfb:B'})
        self.assertEqual(response.status_code,422)
        self.assertEqual(response.json()['detail']['code'],'insufficient_historical_evidence')
        self.assertNotIn('homeWinProbability',response.text)

    def test_signed_isolated_cfb_run_and_tamper_rejection(self):
        model=self.fitted()
        data={'model':model,'home':'cfb:SYNTH-A','away':'cfb:SYNTH-B','eventStart':'2024-03-01T00:00:00Z','simulations':1000,'seed':42}
        response=self.client.post('/cfb/simulate',headers=self.headers,json=data)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['sport'],'CFB')
        self.assertEqual(response.json()['simulations'],1000)
        changed=copy.deepcopy(data);changed['model']['rows'][0]['yards']+=3
        self.assertEqual(self.client.post('/cfb/simulate',headers=self.headers,json=changed).status_code,422)

    def test_synthetic_fixtures_never_produce_deployed_forecasts(self):
        model=self.fitted()
        data={'model':model,'home':'cfb:SYNTH-A','away':'cfb:SYNTH-B','eventStart':'2024-03-01T00:00:00Z','simulations':1000}
        for variable,value in (('RENDER','true'),('VERCEL','1'),('GRIDIRON_CFB_TEST_MODE','')):
            with patch.dict(os.environ,{variable:value}):
                response=self.client.post('/cfb/analyze',headers=self.headers,json=data)
                self.assertEqual(response.status_code,422)
                self.assertIn('Synthetic CFB',response.json()['detail'])

    def test_cfb_does_not_accept_arbitrary_adjustments_or_nfl_artifacts(self):
        model=self.fitted()
        payload={'model':model,'home':'cfb:SYNTH-A','away':'cfb:SYNTH-B','eventStart':'2024-03-01T00:00:00Z','simulations':1000}
        self.assertEqual(self.client.post('/cfb/simulate',headers=self.headers,json={**payload,'windMultiplier':.5}).status_code,422)
        with patch.dict(os.environ,{'GRIDIRON_CFB_TEST_MODE':'1'}):
            from .service import signature
            wrong=copy.deepcopy(model);wrong['sport']='NFL';wrong['signature']=signature(wrong)
            response=self.client.post('/cfb/simulate',headers=self.headers,json={**payload,'model':wrong})
            self.assertEqual(response.status_code,422)
            self.assertIn('separate fitted CFB',response.json()['detail'])


if __name__=='__main__':unittest.main()
