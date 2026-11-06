import contextlib,importlib.util,io,json,os,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('controlled_preflight',Path(__file__).resolve().parents[1]/'scripts/compute-worker.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
class WorkerPreflightTests(unittest.TestCase):
    ENV={'GRIDIRON_COMPUTE_ROLE':'worker','SUPABASE_URL':'https://synthetic.supabase.co','SUPABASE_PUBLISHABLE_KEY':'sb_publishable_SYNTHETIC','GRIDIRON_PUBLIC_INGEST_TOKEN':'SYNTHETIC-capability-abcdefghijklmnopqrstuvwxyz','SIMULATION_SERVICE_TOKEN':'SYNTHETIC-model-token-abcdefghijklmnopqrstuvwxyz'}
    def test_preflight_never_claims_or_starts_model_process(self):
        out=io.StringIO()
        with patch.dict(os.environ,self.ENV,clear=True),patch.object(worker,'rpc',return_value={'role':'cache_and_queue_only','concurrency':1}) as rpc,patch.object(worker.subprocess,'Popen') as launch,contextlib.redirect_stdout(out):worker.main(['--preflight'])
        rpc.assert_called_once_with({'action':'status'});launch.assert_not_called();result=json.loads(out.getvalue());self.assertEqual(result['simulationsStarted'],0);self.assertFalse(result['continuousWorkerActive'])
    def test_both_existing_web_services_are_forbidden(self):
        for service in ['srv-dblsg9gn74is73cjc8lg','srv-dbj680s9v7es7397nv2g']:
            with patch.dict(os.environ,{**self.ENV,'RENDER_SERVICE_ID':service},clear=True),patch.object(worker,'rpc') as rpc,contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):worker.main(['--preflight'])
                rpc.assert_not_called()
    def test_explicit_worker_role_is_required(self):
        with patch.dict(os.environ,{**self.ENV,'GRIDIRON_COMPUTE_ROLE':'web'},clear=True),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):worker.main(['--preflight'])
    def test_no_secret_forwarding_to_http_or_redirected_origins(self):
        for origin in ['http://synthetic.supabase.co','https://username:password@example.test','https://example.test/other?token=bad']:
            with patch.dict(os.environ,{**self.ENV,'SUPABASE_URL':origin},clear=True):
                with self.assertRaises(ValueError):worker.validate_worker_config()
    def test_preflight_does_not_enqueue_refresh(self):
        with patch.dict(os.environ,self.ENV,clear=True),patch.object(worker,'rpc') as rpc,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):worker.main(['--preflight','--refresh'])
            rpc.assert_not_called()
