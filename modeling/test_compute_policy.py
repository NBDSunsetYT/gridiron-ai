"""Compute boundary only; never runs game simulations."""
import os
import unittest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from modeling.service import app, guarded

class HostingComputePolicy(unittest.TestCase):
    def test_vercel_cannot_run_models_even_with_worker_role(self):
        work=Mock()
        with patch.dict(os.environ,{'VERCEL':'1','GRIDIRON_COMPUTE_ROLE':'worker'}):
            with self.assertRaises(HTTPException) as exc:guarded(work)
        self.assertEqual(exc.exception.status_code,409);work.assert_not_called()

    def test_saved_private_job_cannot_bypass_web_boundary(self):
        token='SYNTHETIC-COMPUTE-POLICY-TEST-TOKEN-ONLY'
        with patch.dict(os.environ,{'VERCEL':'1','SIMULATION_SERVICE_TOKEN':token}):
            with TestClient(app) as client:
                response=client.post('/jobs',json={'jobId':'SYNTHETIC','accessToken':'NEVER-A-REAL-SESSION'},headers={'Authorization':'Bearer '+token})
                self.assertEqual(response.status_code,409)

    def test_local_worker_executes_unchanged_callable(self):
        with patch.dict(os.environ,{'VERCEL':'','GRIDIRON_COMPUTE_ROLE':'worker'}):self.assertEqual(guarded(lambda:1234/10000),.1234)

if __name__=='__main__':unittest.main()
