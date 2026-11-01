"""SYNTHETIC authorization and source-boundary mechanics, never model accuracy."""
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from .service import app
from .cfb_public_research import analyze_cfb_targets

class ProbabilityTargetBoundaryTests(unittest.TestCase):
    def test_raw_client_models_and_unknown_fields_are_rejected_before_source_retrieval(self):
        with patch('modeling.cfb_public_research._prepare_cfb_public') as prepare:
            for data in ({'model':{},'contracts':[{},{}]}, {'contracts':[{}]}, {'contracts':[{'kind':'unknown'},{}]}):
                with self.assertRaises(ValueError):analyze_cfb_targets(data)
            prepare.assert_not_called()

    def test_private_target_endpoint_requires_worker_authorization(self):
        with patch.dict(os.environ,{'SIMULATION_SERVICE_TOKEN':'SYNTHETIC-PRIVATE-WORKER-TOKEN-ONLY-123456789'}):
            r=TestClient(app).post('/cfb/public/targets',json={'game':{},'contracts':[{},{}]})
            self.assertIn(r.status_code,(401,403,503))

    def test_verified_targets_share_one_complete_game_simulation_call(self):
        definitions=[{'id':'A','kind':'spread','threshold':0,'direction':'over'}, {'id':'B','kind':'total','threshold':40,'direction':'under'}]
        prepared={'model':{'sha256':'SYNTHETIC-SHA'},'game':{'startTime':'2099-01-01'},'home':'1','away':'2'}
        with patch('modeling.cfb_public_research._prepare_cfb_public',return_value=prepared),patch('modeling.cfb_public_research._research',return_value={'synthetic':True}),patch('modeling.cfb_public_research.simulate_cfb',return_value={'simulations':10000}) as simulate:
            result=analyze_cfb_targets({'game':{},'simulations':10000,'contracts':definitions})
            self.assertEqual(simulate.call_count,1)
            self.assertEqual(simulate.call_args.kwargs['contracts'],definitions)
            self.assertEqual(simulate.call_args.args[3],10000)
            self.assertEqual(result['inputHash'],'SYNTHETIC-SHA')
