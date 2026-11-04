"""SYNTHETIC async durability/auth mechanics. No NFL validation or live claims."""
import base64
import copy
import gzip
import hashlib
import io
import json
import math
import os
from contextlib import redirect_stderr, redirect_stdout
from urllib.parse import parse_qs, urlsplit
import unittest
from unittest.mock import patch

from modeling.cloud_worker import (
    CloudWorker, Config, WorkerError, encode_leaf, decode_leaf, result_proof,
    input_mac, verify_input_proof,
)
from modeling.test_simulator import fixture_csv

OWNER = '10000000-0000-4000-8000-000000000001'
OTHER = '10000000-0000-4000-8000-000000000099'
JOB = '20000000-0000-4000-8000-000000000002'
TOKEN = 'SYNTHETIC-OWNER-JWT-NEVER-PERSIST'
SECRET = 'SYNTHETIC-WORKER-SECRET-0123456789'
ENV = {'SUPABASE_URL': 'https://database.example.test',
       'SUPABASE_PUBLISHABLE_KEY': 'sb_publishable_SYNTHETIC_ONLY',
       'SIMULATION_SERVICE_TOKEN': SECRET}


class DeferredExecutor:
    def __init__(self):
        self.tasks = []

    def __call__(self, work):
        self.tasks.append(work)

    def drain(self):
        while self.tasks:
            self.tasks.pop(0)()


class FakeSupabase:
    """Realistic owner RLS and conditional PATCH matching, not a compute stub."""
    def __init__(self, input_value=None, owner=OWNER):
        self.owner = owner
        self.calls = []
        self.expire_final_writes = False
        self.deny_claim = False
        self.rows = []
        self.add_job(JOB, input_value or fit_input())

    def add_job(self, job_id, input_value, owner=OWNER):
        self.rows.extend([
            {'id': job_id, 'user_id': owner, 'kind': 'simulation_jobs', 'entity_key': '',
             'data': {'id': job_id, 'kind': input_value['action'], 'status': 'queued',
                      'data': {'inputHash': 'SYNTHETIC'}, 'result': None, 'error': None,
                      'createdAt': '2026-01-01T00:00:00Z',
                      'updatedAt': '2026-01-01T00:00:00Z'},
             'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z'},
            {'id': job_id[:-1] + '3', 'user_id': owner, 'kind': 'simulation_inputs',
             'entity_key': job_id, 'data': {'jobId': job_id, 'input': encode_leaf(input_value),
                 'inputProof': {'version': 1, 'algorithm': 'hmac-sha256',
                                'mac': input_mac(owner, job_id, input_value, SECRET)}},
             'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z'},
        ])

    def job(self, job_id=JOB):
        return next(row for row in self.rows if row['kind'] == 'simulation_jobs' and row['id'] == job_id)

    @staticmethod
    def matches(row, key, expected):
        if key in ('select', 'order', 'limit', 'offset'):
            return True
        if not expected.startswith('eq.'):
            raise AssertionError('Unexpected filter ' + key + ': ' + expected)
        value = row
        if key.startswith('data->>'):
            value = row['data'].get(key[7:])
        else:
            value = row.get(key)
        return str(value) == expected[3:]

    def __call__(self, method, path, token, body=None):
        self.calls.append({'method': method, 'path': path, 'body': copy.deepcopy(body)})
        if token != TOKEN:
            raise WorkerError('Invalid synthetic owner token', 401)
        url = urlsplit(path)
        if url.path == '/auth/v1/user':
            return {'id': self.owner}
        if url.path != '/rest/v1/gridiron_records':
            raise AssertionError('Unexpected endpoint ' + path)
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        # A JWT never authorizes a row belonging to another owner.
        rows = [row for row in self.rows if row['user_id'] == self.owner and
                all(self.matches(row, key, value) for key, value in query.items())]
        if method == 'GET':
            self_assert_owner = query.get('user_id')
            if self_assert_owner != 'eq.' + self.owner:
                raise AssertionError('Explicit owner filter was omitted')
            return copy.deepcopy(rows[:int(query.get('limit', str(len(rows))))])
        if method == 'PATCH':
            if query.get('user_id') != 'eq.' + self.owner:
                raise AssertionError('Explicit owner filter was omitted from PATCH')
            if self.deny_claim and body['data'].get('status') == 'running':
                return []
            if self.expire_final_writes and body['data'].get('status') in ('completed', 'failed'):
                raise WorkerError('JWT expired', 401)
            for row in rows:
                row.update(copy.deepcopy(body))
            return [{'id': row['id']} for row in rows]
        raise AssertionError('Unexpected method ' + method)


def fit_input():
    return {'action': 'fit', 'csv': fixture_csv(),
            'source': 'SYNTHETIC ASYNC MECHANICAL FIXTURE ONLY',
            'asOf': '2024-02-01T00:00:00Z'}


class CloudWorkerTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, ENV)
        self.env.start()
        self.config = Config.from_environment(ENV)

    def tearDown(self):
        self.env.stop()

    def test_numeric_unicode_receipt_matches_independent_node_crypto_vector(self):
        result = {'simulations': 1000, 'p': .625, 'negativeZero': -0., 'tiny': 1e-9,
                  'none': None, 'bool': True, 'unicode': '🏈',
                  'nested': {'\ue000': 1, '𐀀': 2}, 'arr': [False, 'élan', 1., -12.25]}
        proof = result_proof(OWNER, JOB, result, SECRET)
        self.assertEqual(proof['version'], 2)
        self.assertEqual(proof['algorithm'], 'hmac-sha256')
        self.assertEqual(proof['mac'], '3918e3c40811e98b3057fb9a89fafd13d0bc7a452507576d892e1107859f8a11')
        self.assertNotEqual(proof['mac'], result_proof(OTHER, JOB, result, SECRET)['mac'])
        self.assertNotEqual(proof['mac'], result_proof(OWNER, JOB[:-1] + '4', result, SECRET)['mac'])
        changed = copy.deepcopy(result); changed['simulations'] += 1
        self.assertNotEqual(proof['mac'], result_proof(OWNER, JOB, changed, SECRET)['mac'])
        with self.assertRaises((ValueError, WorkerError)):
            result_proof(OWNER, JOB, {'p': float('nan')}, SECRET)

    def test_input_receipt_matches_node_crypto_and_rejects_owner_job_or_payload_changes(self):
        value = {'simulations': 1000, 'p': .625, 'negativeZero': -0., 'tiny': 1e-9,
                 'none': None, 'bool': True, 'unicode': '🏈',
                 'nested': {'\ue000': 1, '𐀀': 2}, 'arr': [False, 'élan', 1., -12.25]}
        mac = input_mac(OWNER, JOB, value, SECRET)
        self.assertEqual(mac, 'af0788ecaa39d67ed193d352c376f9c6060824d61d22087f106fc46245d8c9de')
        proof = {'version': 1, 'algorithm': 'hmac-sha256', 'mac': mac}
        verify_input_proof(OWNER, JOB, value, proof, SECRET)
        for owner, job, payload in ((OTHER, JOB, value), (OWNER, JOB[:-1] + '4', value),
                                    (OWNER, JOB, {**value, 'p': .9})):
            with self.assertRaises(WorkerError):
                verify_input_proof(owner, job, payload, proof, SECRET)
        for invalid in (None, {}, {**proof, 'version': True}, {**proof, 'mac': 'x' * 64}):
            with self.assertRaises(WorkerError):
                verify_input_proof(OWNER, JOB, value, invalid, SECRET)

    def test_missing_or_forged_enqueue_receipt_never_claims_saved_input(self):
        transport = FakeSupabase(); executor = DeferredExecutor()
        worker = CloudWorker(self.config, transport=transport, executor=executor)
        saved = next(row for row in transport.rows if row['kind'] == 'simulation_inputs')['data']
        original = copy.deepcopy(saved)
        for altered in ({key: value for key, value in original.items() if key != 'inputProof'},
                        {**original, 'input': {'action': 'fit', 'csv': 'SYNTHETIC edited evidence'}},
                        {**original, 'inputProof': {**original['inputProof'], 'mac': '0' * 64}}):
            saved.clear(); saved.update(copy.deepcopy(altered))
            with self.assertRaises(WorkerError):
                worker.submit(JOB, TOKEN, lambda _: {'never': 'computed'})
            self.assertEqual(transport.job()['data']['status'], 'queued')
            self.assertEqual(executor.tasks, [])
            self.assertFalse(any(call['method'] == 'PATCH' for call in transport.calls))
        saved.clear(); saved.update(original)
        self.assertTrue(worker.submit(JOB, TOKEN, lambda _: {'restored': True})['accepted'])
        executor.drain()
        self.assertEqual(transport.job()['data']['status'], 'completed')

    def test_explicit_nonvercel_request_bound_worker_persists_before_response(self):
        from fastapi.testclient import TestClient
        from modeling import service
        for mode in ({'VERCEL': '0', 'GRIDIRON_WORKER_REQUEST_LIFETIME': '1'},):
            transport = FakeSupabase()
            observations = []
            def compute(payload):
                observations.append(transport.job()['data']['status'])
                self.assertEqual(payload['action'], 'fit')
                return {'completedBeforeResponse': True}
            with patch.dict(os.environ, mode), patch.object(service, 'cloud_worker', None), \
                    patch('modeling.cloud_worker.SupabaseTransport', return_value=transport), \
                    patch.object(service, 'compute_saved_input', side_effect=compute):
                with TestClient(service.app) as client:
                    response = client.post('/jobs', headers={'Authorization': 'Bearer ' + SECRET},
                                           json={'jobId': JOB, 'accessToken': TOKEN})
                    self.assertEqual(response.status_code, 202)
                    self.assertTrue(response.json()['accepted'])
                    self.assertEqual(observations, ['running'])
                    saved = transport.job()['data']
                    self.assertEqual(saved['status'], 'completed')
                    self.assertEqual(decode_leaf(saved['result']), {'completedBeforeResponse': True})
                    self.assertEqual(saved['resultProof']['mac'],
                                     result_proof(OWNER, JOB, saved['result'], SECRET)['mac'])
                    self.assertTrue(service.cloud_worker.wait_for_idle(.1))
                    self.assertNotIn(TOKEN, json.dumps(transport.rows))

    def test_render_execution_remains_deferred_when_not_request_bound(self):
        from modeling import service
        transport = FakeSupabase()
        with patch.dict(os.environ, {'VERCEL': '0', 'GRIDIRON_WORKER_REQUEST_LIFETIME': '0'}), \
                patch.object(service, 'cloud_worker', None), \
                patch('modeling.cloud_worker.SupabaseTransport', return_value=transport), \
                patch.object(CloudWorker, '_spawn') as spawn:
            worker = service.get_cloud_worker()
            worker.submit(JOB, TOKEN, lambda _: {'result': 'SYNTHETIC'})
            self.assertEqual(transport.job()['data']['status'], 'running')
            self.assertIsNone(transport.job()['data']['result'])
            spawn.assert_called_once()
            spawn.call_args.args[0]()
            self.assertEqual(transport.job()['data']['status'], 'completed')

    def test_bounded_codec_preserves_unicode_and_rejects_tamper_or_decompression_bombs(self):
        original = {'source': 'SYNTHETIC 🏈', 'rows': list(range(30000))}
        encoded = encode_leaf(original)
        self.assertEqual(encoded['_gridironGzipJson'], 1)
        self.assertEqual(decode_leaf(encoded), original)
        damaged = {**encoded, 'sha256': '0' * 64}
        with self.assertRaises((WorkerError, ValueError)):
            decode_leaf(damaged)
        with self.assertRaises((WorkerError, ValueError)):
            decode_leaf({**encoded, 'bytes': 20_000_001})
        raw = b'x' * 500000
        bomb = {'_gridironGzipJson': 1, 'sha256': hashlib.sha256(raw).hexdigest(),
                'bytes': 8, 'base64': base64.b64encode(gzip.compress(raw)).decode()}
        with self.assertRaises((WorkerError, ValueError)):
            decode_leaf(bomb)
        self.assertEqual(decode_leaf({'ordinary': True}), {'ordinary': True})

    def test_configuration_rejects_untrusted_endpoint_admin_key_and_missing_credentials(self):
        for invalid in ({}, {**ENV, 'SUPABASE_URL': 'http://remote.example.test'},
                        {**ENV, 'SUPABASE_PUBLISHABLE_KEY': 'sb_secret_SYNTHETIC_ADMIN'},
                        {**ENV, 'SIMULATION_SERVICE_TOKEN': 'short'}):
            with self.assertRaises((WorkerError, ValueError)):
                Config.from_environment(invalid)

    def test_acceptance_is_deferred_and_real_fixture_fit_and_shared_game_stats_persist(self):
        from modeling.service import compute_saved_input
        transport = FakeSupabase(); executor = DeferredExecutor()
        worker = CloudWorker(self.config, transport=transport, executor=executor)
        result = worker.submit(JOB, TOKEN, compute_saved_input)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['status'], 'running')
        self.assertEqual(transport.job()['data']['status'], 'running')
        self.assertIsNone(transport.job()['data']['result'])
        self.assertEqual(len(executor.tasks), 1)
        executor.drain()
        fitted_job = transport.job()['data']
        self.assertEqual(fitted_job['status'], 'completed')
        fitted = decode_leaf(fitted_job['result'])
        self.assertTrue(fitted['model']['signature'])
        self.assertEqual(fitted_job['resultProof']['mac'], result_proof(OWNER, JOB, fitted, SECRET)['mac'])
        simulation_id = '30000000-0000-4000-8000-000000000004'
        transport.add_job(simulation_id, {'action': 'simulate', 'model': fitted['model'],
                           'home': 'SYNTH-A', 'away': 'SYNTH-B', 'simulations': 1000,
                           'seed': 17, 'eventStart': '2024-03-01T00:00:00Z',
                           'representativeGames': 1, 'injuryEntityKeys': []})
        self.assertTrue(worker.submit(simulation_id, TOKEN, compute_saved_input)['accepted'])
        executor.drain()
        saved = transport.job(simulation_id)['data']; self.assertEqual(saved['status'], 'completed')
        value = decode_leaf(saved['result']); self.assertEqual(value['simulations'], 1000)
        self.assertEqual(sum(row['count'] for row in value['scoreDistributions']['SYNTH-A']['histogram']), 1000)
        trace = value['representativeGames'][0]
        self.assertEqual(sum(p.get('passingYards', 0) for p in trace['players'].values()),
                         sum(p.get('receivingYards', 0) for p in trace['players'].values()))
        self.assertEqual(sum(p.get('completions', 0) for p in trace['players'].values()),
                         sum(p.get('receptions', 0) for p in trace['players'].values()))
        self.assertNotIn(TOKEN, json.dumps(transport.rows))
        self.assertNotIn(SECRET, json.dumps(transport.rows))

    def test_owner_verification_and_conditional_claim_prevent_cross_account_or_duplicate_work(self):
        transport = FakeSupabase(); executor = DeferredExecutor()
        worker = CloudWorker(self.config, transport=transport, executor=executor)
        with self.assertRaises(WorkerError) as invalid:
            worker.submit(JOB, 'SYNTHETIC-INVALID-JWT', lambda _: {'never': 'computed'})
        self.assertIn(invalid.exception.status, (401, 403))
        self.assertEqual(len(executor.tasks), 0)
        other_transport = FakeSupabase(owner=OTHER)
        with self.assertRaises(WorkerError):
            CloudWorker(self.config, transport=other_transport, executor=executor).submit(JOB, TOKEN, lambda _: {})
        self.assertEqual(len(executor.tasks), 0)
        transport.deny_claim = True
        response = worker.submit(JOB, TOKEN, lambda _: {})
        self.assertFalse(response['accepted']); self.assertEqual(len(executor.tasks), 0)
        self.assertEqual(transport.job()['data']['status'], 'queued')
        transport.deny_claim = False
        self.assertTrue(worker.submit(JOB, TOKEN, lambda _: {'value': 1})['accepted'])
        self.assertFalse(worker.submit(JOB, TOKEN, lambda _: {'value': 2})['accepted'])
        self.assertEqual(len(executor.tasks), 1)
        claims = [call for call in transport.calls if call['method'] == 'PATCH' and call['body']['data'].get('status') == 'running']
        self.assertTrue(all(parse_qs(urlsplit(call['path']).query).get('data->>status') == ['eq.queued'] for call in claims))
        executor.drain(); self.assertEqual(decode_leaf(transport.job()['data']['result']), {'value': 1})

    def test_expired_final_write_never_claims_completion_and_preserves_replay_inputs(self):
        transport = FakeSupabase(); executor = DeferredExecutor()
        worker = CloudWorker(self.config, transport=transport, executor=executor)
        worker.submit(JOB, TOKEN, lambda _: {'value': 1})
        before_inputs = copy.deepcopy([r for r in transport.rows if r['kind'] == 'simulation_inputs'])
        transport.expire_final_writes = True
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            executor.drain()
        self.assertNotEqual(transport.job()['data']['status'], 'completed')
        self.assertIsNone(transport.job()['data']['result'])
        self.assertEqual([r for r in transport.rows if r['kind'] == 'simulation_inputs'], before_inputs)
        self.assertNotIn(TOKEN, output.getvalue())
        self.assertNotIn(SECRET, output.getvalue())

    def test_replaced_lease_cannot_be_overwritten_by_an_old_worker_result(self):
        transport = FakeSupabase(); executor = DeferredExecutor()
        worker = CloudWorker(self.config, transport=transport, executor=executor)
        worker.submit(JOB, TOKEN, lambda _: {'value': 1})
        claimed = transport.job()['data']; claimed['workerLease'] = 'SYNTHETIC-NEW-LEASE'
        executor.drain()
        self.assertEqual(transport.job()['data']['workerLease'], 'SYNTHETIC-NEW-LEASE')
        self.assertEqual(transport.job()['data']['status'], 'running')
        self.assertIsNone(transport.job()['data']['result'])
        response = worker.submit(JOB, TOKEN, lambda _: {'value': 2})
        self.assertFalse(response['accepted'])
        self.assertEqual(transport.job()['data']['workerLease'], 'SYNTHETIC-NEW-LEASE')
        self.assertEqual(transport.job()['data']['status'], 'running')

    def test_expired_save_can_reconcile_and_run_a_fresh_lease_without_old_failure_replay(self):
        transport = FakeSupabase(); executor = DeferredExecutor()
        worker = CloudWorker(self.config, transport=transport, executor=executor)
        worker.submit(JOB, TOKEN, lambda _: {'attempt': 1})
        transport.expire_final_writes = True; executor.drain()
        self.assertEqual(transport.job()['data']['status'], 'running')
        transport.expire_final_writes = False
        reconciled = worker.submit(JOB, TOKEN, lambda _: {'attempt': 99})
        self.assertFalse(reconciled['accepted'])
        self.assertEqual(transport.job()['data']['status'], 'failed')
        transport.job()['data']['status'] = 'queued'
        self.assertTrue(worker.submit(JOB, TOKEN, lambda _: {'attempt': 2})['accepted'])
        self.assertFalse(worker.submit(JOB, TOKEN, lambda _: {'attempt': 3})['accepted'])
        self.assertEqual(transport.job()['data']['status'], 'running')
        executor.drain()
        self.assertEqual(transport.job()['data']['status'], 'completed')
        self.assertEqual(decode_leaf(transport.job()['data']['result']), {'attempt': 2})

    def test_shutdown_requeues_the_owned_lease_and_old_execution_never_commits_completion(self):
        transport = FakeSupabase(); executor = DeferredExecutor()
        worker = CloudWorker(self.config, transport=transport, executor=executor)
        worker.submit(JOB, TOKEN, lambda _: {'attempt': 1})
        original_inputs = copy.deepcopy([r for r in transport.rows if r['kind'] == 'simulation_inputs'])
        worker.shutdown()
        self.assertEqual(transport.job()['data']['status'], 'queued')
        with self.assertRaises(WorkerError):
            worker.submit(JOB, TOKEN, lambda _: {'attempt': 2})
        executor.drain()
        self.assertEqual(transport.job()['data']['status'], 'queued')
        self.assertIsNone(transport.job()['data']['result'])
        self.assertEqual([r for r in transport.rows if r['kind'] == 'simulation_inputs'], original_inputs)
        new_executor = DeferredExecutor()
        replacement = CloudWorker(self.config, transport=transport, executor=new_executor)
        self.assertTrue(replacement.submit(JOB, TOKEN, lambda _: {'attempt': 3})['accepted'])
        new_executor.drain()
        self.assertEqual(transport.job()['data']['status'], 'completed')
        self.assertEqual(decode_leaf(transport.job()['data']['result']), {'attempt': 3})

    def test_untrusted_or_mismatched_saved_input_never_starts_compute_or_claims_the_job(self):
        transport = FakeSupabase(); executor = DeferredExecutor()
        worker = CloudWorker(self.config, transport=transport, executor=executor)
        source = next(row for row in transport.rows if row['kind'] == 'simulation_inputs')
        packed = source['data']['input']
        self.assertEqual(packed['_gridironGzipJson'], 1)
        source['data']['input'] = {**packed, 'sha256': '0' * 64}
        with self.assertRaises(WorkerError):
            worker.submit(JOB, TOKEN, lambda _: {'never': 'computed'})
        self.assertEqual(transport.job()['data']['status'], 'queued')
        self.assertEqual(executor.tasks, [])
        source['data']['input'] = {'action': 'simulate', 'model': {}}
        with self.assertRaises(WorkerError):
            worker.submit(JOB, TOKEN, lambda _: {'never': 'computed'})
        self.assertEqual(transport.job()['data']['status'], 'queued')
        self.assertEqual(executor.tasks, [])

    def test_one_active_compute_keeps_other_job_queued_and_legacy_engine_busy_is_retryable(self):
        from fastapi import HTTPException
        transport = FakeSupabase(); executor = DeferredExecutor()
        worker = CloudWorker(self.config, transport=transport, executor=executor)
        def busy(_):
            raise HTTPException(429, 'SYNTHETIC engine already running')
        self.assertTrue(worker.submit(JOB, TOKEN, busy)['accepted'])
        second_id = '30000000-0000-4000-8000-000000000004'
        transport.add_job(second_id, fit_input())
        waiting = worker.submit(second_id, TOKEN, lambda _: {'value': 2})
        self.assertFalse(waiting['accepted'])
        self.assertEqual(waiting['status'], 'queued')
        self.assertEqual(transport.job(second_id)['data']['status'], 'queued')
        self.assertEqual(len(executor.tasks), 1)
        executor.drain()
        self.assertEqual(transport.job()['data']['status'], 'queued')
        self.assertIsNone(transport.job()['data']['result'])
        self.assertTrue(worker.submit(second_id, TOKEN, lambda _: {'value': 2})['accepted'])
        executor.drain()
        self.assertEqual(transport.job(second_id)['data']['status'], 'completed')

    def test_private_jobs_endpoint_rejects_missing_bearer_and_malformed_dispatch_without_network(self):
        from fastapi.testclient import TestClient
        from modeling import service
        with patch('modeling.cloud_worker.urllib.request.urlopen', side_effect=AssertionError('Unexpected external request')):
            with TestClient(service.app) as client:
                self.assertEqual(client.post('/jobs', json={'jobId': JOB, 'accessToken': TOKEN}).status_code, 401)
                malformed = client.post('/jobs', headers={'Authorization': 'Bearer ' + SECRET},
                                        json={'jobId': JOB, 'accessToken': TOKEN, 'callbackUrl': 'https://untrusted.example.test'})
                self.assertEqual(malformed.status_code, 400)

    def test_private_jobs_endpoint_reports_missing_cloud_configuration_without_fake_acceptance(self):
        from fastapi.testclient import TestClient
        from modeling import service
        with patch.object(service, 'cloud_worker', None), patch.dict(os.environ, {'SUPABASE_URL': '', 'SUPABASE_PUBLISHABLE_KEY': ''}):
            with patch('modeling.cloud_worker.urllib.request.urlopen', side_effect=AssertionError('Unexpected external request')):
                with TestClient(service.app) as client:
                    response = client.post('/jobs', headers={'Authorization': 'Bearer ' + SECRET},
                                           json={'jobId': JOB, 'accessToken': TOKEN})
                    self.assertEqual(response.status_code, 503)
                    self.assertNotIn(TOKEN, response.text)
                    self.assertNotIn(SECRET, response.text)

    def test_unexpected_compute_failure_is_safe_and_not_a_fabricated_result(self):
        transport = FakeSupabase(); executor = DeferredExecutor()
        worker = CloudWorker(self.config, transport=transport, executor=executor)
        def fail(_):
            raise RuntimeError('SYNTHETIC failure containing ' + TOKEN + SECRET)
        worker.submit(JOB, TOKEN, fail)
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            executor.drain()
        saved = transport.job()['data']; self.assertEqual(saved['status'], 'failed')
        self.assertIsNone(saved['result']); self.assertNotIn(TOKEN, json.dumps(saved))
        self.assertNotIn(SECRET, json.dumps(saved)); self.assertNotIn(TOKEN, output.getvalue())


if __name__ == '__main__':
    unittest.main()
