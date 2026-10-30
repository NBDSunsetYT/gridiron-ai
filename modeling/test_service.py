"""HTTP boundary tests. SYNTHETIC mechanical data, never NFL model validation."""
import copy
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from modeling.service import app
from modeling.test_simulator import fixture_csv


class ServiceTests(unittest.TestCase):
    def test_model_signature_survives_javascript_number_normalization(self):
        from modeling.service import signature
        model={'signatureVersion':'numeric-canonical-v1','value':1.0,'tiny':1e-9,'zero':-0.0,'list':[2.,True,None]}
        rewritten={'signatureVersion':'numeric-canonical-v1','value':1,'tiny':.000000001,'zero':0,'list':[2,True,None]}
        with patch.dict(os.environ,{'SIMULATION_SERVICE_TOKEN':'synthetic-test-service-token-not-for-production-8240'}):
            self.assertEqual(signature(model),signature(rewritten))
    def setUp(self):
        self.env = patch.dict(os.environ, {"SIMULATION_SERVICE_TOKEN": "synthetic-test-service-token-not-for-production-8240"})
        self.env.start()
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + os.environ["SIMULATION_SERVICE_TOKEN"]}

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def test_private_service_rejects_missing_authentication(self):
        self.assertEqual(self.client.post('/fit', json={}).status_code, 401)
        self.assertEqual(self.client.post('/simulate', json={}).status_code, 401)
        self.assertEqual(self.client.post('/trace',json={}).status_code,401)
        self.assertEqual(self.client.post('/models/predict',json={}).status_code,401)
        self.assertEqual(self.client.post('/models/benchmark',json={}).status_code,401)

    def test_fit_signed_simulation_and_tamper_rejection(self):
        fit = self.client.post('/fit', headers=self.headers, json={
            'csv': fixture_csv(), 'source': 'SYNTHETIC MECHANICAL HTTP TEST ONLY',
            'asOf': '2024-02-01T00:00:00Z'})
        self.assertEqual(fit.status_code, 200, fit.text)
        model = fit.json()['model']
        self.assertTrue(model['signature'])
        body = {'model': model, 'home': 'SYNTH-A', 'away': 'SYNTH-B', 'simulations': 1000,
                'seed': 11, 'eventStart': '2024-03-01T00:00:00Z'}
        result = self.client.post('/simulate', headers=self.headers, json=body)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['simulations'], 1000)
        self.assertEqual(sum(r['count'] for r in result.json()['scoreDistributions']['SYNTH-A']['histogram']), 1000)
        tampered = copy.deepcopy(body)
        tampered['model']['rows'][0]['yards'] += 5
        self.assertEqual(self.client.post('/simulate', headers=self.headers, json=tampered).status_code, 422)

    def test_no_missing_data_substitution(self):
        response = self.client.post('/fit', headers=self.headers, json={
            'csv': 'game_id\nnot-nfl-data\n', 'source': 'SYNTHETIC TEST', 'asOf': '2024-02-01T00:00:00Z'})
        self.assertEqual(response.status_code, 422)
        self.assertIn('Missing CSV columns', response.json()['detail'])

    def test_representative_trace_and_unsupported_assumption_rejection(self):
        fitted=self.client.post('/fit',headers=self.headers,json={'csv':fixture_csv(),'source':'SYNTHETIC HTTP TRACE TEST','asOf':'2024-02-01T00:00:00Z'}).json()
        payload={'model':fitted['model'],'home':'SYNTH-A','away':'SYNTH-B','eventStart':'2024-03-01T00:00:00Z'}
        result=self.client.post('/trace',headers=self.headers,json=payload)
        self.assertEqual(result.status_code,200,result.text)
        self.assertGreater(len(result.json()['games'][0]['plays']),30)
        self.assertNotIn('homeWinProbability',result.json())
        unsupported=self.client.post('/simulate',headers=self.headers,json={**payload,'simulations':1000,'weatherMultiplier':.7})
        self.assertEqual(unsupported.status_code,422)
        self.assertIn('not silently applied',unsupported.json()['detail'])

    def test_signed_model_prediction_and_mutation_boundary(self):
        from modeling.advanced import VERSION,FEATURES
        from modeling.test_advanced import row
        from modeling.service import signature
        dimensions=1+2+len(FEATURES)
        model={'version':VERSION,'signatureVersion':'numeric-canonical-v1','asOf':'2025-01-01T00:00:00Z','history':[row(i) for i in range(20)],'trainingThroughSeason':2023,'calibrationSeason':2024,
               'modelOrder':['bayesian','regularized','boosting'],'ensembleWeights':[.3,.3,.4],
               'calibrators':{k:{'slope':1.,'intercept':0.} for k in ['bayesian','regularized','boosting']},
               'models':{'bayesian':{'kind':'bayesian_team_strength_laplace','teams':['A','H'],'mean':[0.]*len(FEATURES),'scale':[1.]*len(FEATURES),'coefficients':[0.]*dimensions,'covariance':[[.01 if i==j else 0. for i in range(dimensions)] for j in range(dimensions)]},
                         'regularized':{'kind':'regularized_recency_team_features','mean':[0.]*len(FEATURES),'scale':[1.]*len(FEATURES),'coefficients':[0.]*len(FEATURES),'intercept':0.},
                         'boosting':{'kind':'gradient_boosted_game_features','baseLogit':0.,'learningRate':.05,'trees':[]}}}
        model['signature']=signature(model)
        payload={'model':model,'home':'H','away':'A','eventStart':'2026-01-01T00:00:00Z'}
        response=self.client.post('/models/predict',headers=self.headers,json=payload)
        self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(response.json()['productionEligible'])
        self.assertIsNone(response.json()['ensembleParameterInterval'])
        payload['model']['models']['regularized']['intercept']=1.
        self.assertEqual(self.client.post('/models/predict',headers=self.headers,json=payload).status_code,422)


if __name__ == '__main__':
    unittest.main()
