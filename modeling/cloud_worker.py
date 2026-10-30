"""Owner-scoped durable compute dispatch for the existing private FastAPI app.

Supabase stores queue inputs and results. Memory holds only active execution and
an ephemeral owner JWT; no administrative or refresh credential is used.
"""
import base64
import gzip
import hashlib
import hmac
import io
import json
import math
import os
import re
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

LEAF_LIMIT = 20_000_000
WIRE_LIMIT = 30_000_000
COMPRESSION_THRESHOLD = 128_000
MARKER = '_gridironGzipJson'


class WorkerError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Config:
    url: str
    publishable_key: str = field(repr=False)
    secret: str = field(repr=False)

    @classmethod
    def from_environment(cls, env=None):
        env = os.environ if env is None else env
        url, key, secret = (env.get(k, '') for k in ('SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY', 'SIMULATION_SERVICE_TOKEN'))
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
            raise WorkerError('Async compute requires a configured HTTPS Supabase origin.')
        if not key or key.startswith('sb_secret_'):
            raise WorkerError('Async compute requires a server-held Supabase publishable key, never a service-role key.')
        if not key.startswith('sb_publishable_'):
            try:
                value = key.split('.')[1]
                role = json.loads(base64.urlsafe_b64decode(value + '=' * (-len(value) % 4)))['role']
            except (ValueError, KeyError, IndexError, TypeError):
                role = None
            if role != 'anon':
                raise WorkerError('Async compute requires a Supabase publishable or legacy anonymous key.')
        if not isinstance(secret, str) or len(secret) < 32:
            raise WorkerError('Async compute requires a stable private simulation token.')
        return cls(url.rstrip('/'), key, secret)


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _load(raw):
    def invalid(_):
        raise ValueError('Nonfinite JSON')
    return json.loads(raw, parse_constant=invalid)


def encode_leaf(value):
    raw = _json(value)
    if len(raw) > LEAF_LIMIT:
        raise WorkerError('Complete research evidence exceeds the supported recovery bound. No truncated result was saved.', 413)
    if len(raw) < COMPRESSION_THRESHOLD:
        return value
    return {MARKER: 1, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
            'base64': base64.b64encode(gzip.compress(raw, compresslevel=6, mtime=0)).decode('ascii')}


def decode_leaf(value):
    if not isinstance(value, dict) or value.get(MARKER) != 1 or isinstance(value.get(MARKER), bool):
        return value
    size = value.get('bytes')
    if set(value) != {MARKER, 'sha256', 'bytes', 'base64'} or isinstance(size, bool) or not isinstance(size, int) or not 0 <= size <= LEAF_LIMIT or not isinstance(value.get('base64'), str) or len(value['base64']) > (LEAF_LIMIT * 4 + 2) // 3 + 8 or not isinstance(value.get('sha256'), str) or not re.fullmatch('[a-f0-9]{64}', value['sha256']):
        raise WorkerError('Saved research encoding exceeds the supported recovery bound or is invalid.', 422)
    try:
        compressed = base64.b64decode(value['base64'], validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            raw = stream.read(min(LEAF_LIMIT, size) + 1)
        if len(raw) != size or not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), value['sha256']):
            raise ValueError('Integrity mismatch')
        return _load(raw)
    except (ValueError, OSError, EOFError, UnicodeError, RecursionError) as error:
        raise WorkerError('Saved research evidence failed its encoding integrity check.', 422) from error


def _write_tree(value, write):
    # Stream the canonical tree: a large fit need not allocate a second expanded
    # hierarchy just to generate the authenticated receipt on a 512 MB instance.
    if value is None:
        write(b'["null"]')
    elif isinstance(value, bool):
        write(b'["bool",true]' if value else b'["bool",false]')
    elif isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('Nonfinite result number')
        if number == 0:
            number = 0.0
        write(b'["number",' + _json(struct.pack('>d', number).hex()) + b']')
    elif isinstance(value, str):
        write(b'["string",' + _json(value) + b']')
    elif isinstance(value, list):
        write(b'["array",[')
        for index, item in enumerate(value):
            if index:
                write(b',')
            _write_tree(item, write)
        write(b']]')
    elif isinstance(value, dict) and all(isinstance(k, str) for k in value):
        write(b'["object",[')
        for index, key in enumerate(sorted(value, key=lambda k: k.encode('utf-16-be'))):
            if index:
                write(b',')
            write(b'[' + _json(key) + b',')
            _write_tree(value[key], write)
            write(b']')
        write(b']]')
    else:
        raise ValueError('Unsupported result value')


def canonical_payload(value):
    stream = io.BytesIO()
    _write_tree(value, stream.write)
    return stream.getvalue()


def result_proof(owner_id, job_id, result, secret):
    digest = hmac.new(secret.encode('utf-8'), digestmod=hashlib.sha256)
    digest.update(('GRIDIRON-CLOUD-RESULT-V2\n' + owner_id + '\n' + job_id + '\n').encode('utf-8'))
    _write_tree(result, digest.update)
    return {'version': 2, 'algorithm': 'hmac-sha256', 'mac': digest.hexdigest()}


def input_mac(owner_id, job_id, payload, secret):
    digest = hmac.new(secret.encode('utf-8'), digestmod=hashlib.sha256)
    digest.update(('GRIDIRON-CLOUD-INPUT-V1\n' + owner_id + '\n' + job_id + '\n').encode('utf-8'))
    _write_tree(payload, digest.update)
    return digest.hexdigest()


def verify_input_proof(owner_id, job_id, payload, proof, secret):
    if not isinstance(proof, dict) or proof.get('version') != 1 or isinstance(proof.get('version'), bool) or proof.get('algorithm') != 'hmac-sha256' or not isinstance(proof.get('mac'), str) or not re.fullmatch('[a-f0-9]{64}', proof['mac']):
        raise WorkerError('The saved input lacks an authenticated enqueue receipt. Resubmit the original evidence as a new job.', 422)
    try:
        expected = input_mac(owner_id, job_id, payload, secret)
    except (ValueError, OverflowError, TypeError, UnicodeError, RecursionError):
        raise WorkerError('Saved input cannot be authenticated. No unsupported or edited evidence was executed.', 422) from None
    if not hmac.compare_digest(expected, proof['mac']):
        raise WorkerError('The saved input enqueue receipt is invalid. No edited evidence was executed.', 422)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _path(filters):
    return '/rest/v1/gridiron_records?' + urllib.parse.urlencode(filters)


class SupabaseTransport:
    def __init__(self, config):
        self.config = config

    def __call__(self, method, path, token, body=None):
        if not path.startswith(('/auth/v1/user', '/rest/v1/gridiron_records?')):
            raise WorkerError('Unsupported private worker operation.', 400)
        headers = {'apikey': self.config.publishable_key, 'Authorization': 'Bearer ' + token,
                   'Accept': 'application/json', 'Content-Type': 'application/json'}
        if method == 'PATCH':
            headers['Prefer'] = 'return=representation'
        request = urllib.request.Request(self.config.url + path, method=method, headers=headers,
                                         data=None if body is None else _json(body))
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read(WIRE_LIMIT + 1)
            if len(raw) > WIRE_LIMIT:
                raise WorkerError('Supabase evidence response exceeds the supported recovery bound.', 413)
            return _load(raw)
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                raise WorkerError('Owner authentication expired or was rejected. Sign in again and resume the saved job.', error.code) from None
            raise WorkerError('Supabase could not complete the private worker operation; saved evidence remains intact.', 503) from None
        except (OSError, ValueError, UnicodeError):
            raise WorkerError('Supabase was unavailable or returned an invalid response; saved evidence remains intact.', 503) from None


class CloudWorker:
    def __init__(self, config, transport=None, executor=None):
        self.config = config
        self.transport = transport or SupabaseTransport(config)
        self.executor = executor or self._spawn
        self._state_lock = threading.Lock()
        self._active = {}
        self._failures = {}
        self._stopping = False

    @staticmethod
    def _spawn(work):
        threading.Thread(target=work, daemon=True, name='gridiron-cloud-compute').start()

    def submit(self, job_id, access_token, compute):
        try:
            if str(uuid.UUID(job_id)) != job_id:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise WorkerError('A valid saved job identifier is required.', 400) from None
        if not isinstance(access_token, str) or not 1 <= len(access_token) <= 16000 or any(ord(c) < 33 or ord(c) > 126 for c in access_token):
            raise WorkerError('A valid owner access token is required.', 401)
        user = self.transport('GET', '/auth/v1/user', access_token)
        owner = user.get('id') if isinstance(user, dict) else None
        try:
            owner = str(uuid.UUID(owner))
        except (ValueError, TypeError, AttributeError):
            raise WorkerError('The owner identity could not be independently verified.', 401) from None
        filters = {'id': 'eq.' + job_id, 'user_id': 'eq.' + owner, 'kind': 'eq.simulation_jobs', 'select': '*'}
        rows = self.transport('GET', _path(filters), access_token)
        if not isinstance(rows, list) or len(rows) != 1 or rows[0].get('id') != job_id or rows[0].get('user_id') != owner:
            raise WorkerError('Owned saved simulation job not found.', 404)
        job = rows[0].get('data')
        if not isinstance(job, dict) or job.get('kind') not in ('fit', 'simulate'):
            raise WorkerError('The saved job is not a supported statistical fit or simulation.', 422)
        key = (owner, job_id)
        with self._state_lock:
            if self._stopping:
                raise WorkerError('The compute service is shutting down; the saved job can be resumed.', 503)
            failure = self._failures.get(key)
            if failure and job.get('status') == 'running' and job.get('workerLease') == failure['lease']:
                failed = {**job, 'status': 'failed', 'error': failure['message'], 'updatedAt': _now()}
                self._write(key, failure['lease'], access_token, failed)
                self._failures.pop(key, None)
                return {'jobId': job_id, 'status': 'failed', 'accepted': False}
            if job.get('status') != 'queued':
                return {'jobId': job_id, 'status': job.get('status'), 'accepted': False}
            if self._active:
                return {'jobId': job_id, 'status': 'queued', 'accepted': False, 'reason': 'engine_busy'}
            self._active[key] = {'token': access_token, 'data': job}
        try:
            inputs = self.transport('GET', _path({'user_id': 'eq.' + owner, 'kind': 'eq.simulation_inputs',
                                                  'entity_key': 'eq.' + job_id, 'order': 'created_at.desc,id.desc', 'limit': 1, 'select': '*'}), access_token)
            if not isinstance(inputs, list) or len(inputs) != 1 or inputs[0].get('user_id') != owner:
                raise WorkerError('Complete saved simulation input is unavailable.', 422)
            saved = inputs[0].get('data', {})
            payload = decode_leaf(saved.get('input'))
            verify_input_proof(owner, job_id, payload, saved.get('inputProof'), self.config.secret)
            if saved.get('jobId') != job_id or not isinstance(payload, dict) or payload.get('action') != job['kind']:
                raise WorkerError('Saved input does not match the queued job.', 422)
            with self._state_lock:
                if self._stopping:
                    raise WorkerError('The compute service is shutting down; original inputs remain queued.', 503)
            lease, stamp = str(uuid.uuid4()), _now()
            claimed = {**job, 'status': 'running', 'workerLease': lease, 'updatedAt': stamp, 'error': None}
            changed = self.transport('PATCH', _path({**filters, 'data->>status': 'eq.queued'}), access_token,
                                     {'data': claimed, 'updated_at': stamp})
            if not isinstance(changed, list) or not changed:
                with self._state_lock:
                    self._active.pop(key, None)
                return {'jobId': job_id, 'status': 'queued', 'accepted': False, 'reason': 'claim_lost'}
            with self._state_lock:
                self._failures.pop(key, None)
                self._active[key] = {'token': access_token, 'data': claimed, 'lease': lease, 'stop_event': threading.Event()}
                stopping = self._stopping
            if stopping:
                self._write(key, lease, access_token, {**claimed, 'status': 'queued', 'error': 'Compute was interrupted by service shutdown. Resume the original saved input.', 'updatedAt': _now()})
                with self._state_lock:
                    self._active.pop(key, None)
                return {'jobId': job_id, 'status': 'queued', 'accepted': False, 'reason': 'service_shutdown'}
            self.executor(lambda: self._execute(key, claimed, payload, access_token, compute))
            return {'jobId': job_id, 'status': 'running', 'accepted': True}
        except Exception:
            with self._state_lock:
                self._active.pop(key, None)
            raise

    def _write(self, key, lease, token, data):
        owner, job = key
        filters = {'id': 'eq.' + job, 'user_id': 'eq.' + owner, 'kind': 'eq.simulation_jobs',
                   'data->>status': 'eq.running', 'data->>workerLease': 'eq.' + lease, 'select': 'id'}
        changed = self.transport('PATCH', _path(filters), token, {'data': data, 'updated_at': data['updatedAt']})
        if not isinstance(changed, list) or not changed:
            raise WorkerError('The worker lease changed; no stale result was committed.', 409)

    def _execute(self, key, claimed, payload, token, compute):
        with self._state_lock:
            entry = self._active.get(key)
            stop_event = entry.get('stop_event') if entry else threading.Event()
        def heartbeat():
            while not stop_event.wait(60):
                try:
                    self._write(key, claimed['workerLease'], token, {**claimed, 'updatedAt': _now()})
                except Exception:
                    return
        threading.Thread(target=heartbeat, daemon=True, name='gridiron-cloud-heartbeat').start()
        try:
            result = compute(payload)
            if not isinstance(result, dict):
                raise ValueError('Unsupported result')
            completed = {**claimed, 'status': 'completed', 'result': encode_leaf(result),
                         'resultProof': result_proof(key[0], key[1], result, self.config.secret),
                         'error': None, 'updatedAt': _now()}
            with self._state_lock:
                stopping = self._stopping
            if stopping:
                return
            self._write(key, claimed['workerLease'], token, completed)
        except Exception as error:
            busy = getattr(error, 'status_code', None) == 429
            message = ('The statistical engine is busy; original inputs remain queued for retry.' if busy else
                       'Compute or result persistence failed. Original inputs remain saved; sign in and retry after checking source evidence and service availability.')
            failed = {**claimed, 'status': 'queued' if busy else 'failed', 'result': None,
                      'error': message, 'updatedAt': _now()}
            try:
                self._write(key, claimed['workerLease'], token, failed)
            except Exception:
                # A revoked/expired owner token must never be replaced with admin
                # credentials. A later verified owner can reconcile this failure.
                with self._state_lock:
                    if len(self._failures) >= 100:
                        self._failures.pop(next(iter(self._failures)))
                    self._failures[key] = {'lease': claimed['workerLease'], 'message': message}
        finally:
            stop_event.set()
            with self._state_lock:
                self._active.pop(key, None)

    def shutdown(self):
        with self._state_lock:
            self._stopping = True
            active = list(self._active.items())
        for key, value in active:
            if 'stop_event' in value:
                value['stop_event'].set()
            if 'lease' not in value:
                continue
            queued = {**value['data'], 'status': 'queued', 'error': 'Compute was interrupted by service shutdown. Resume the original saved input.', 'updatedAt': _now()}
            try:
                self._write(key, value['lease'], value['token'], queued)
            except Exception:
                pass  # Durable input and running lease remain recoverable.

    def wait_for_idle(self, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._state_lock:
                if not self._active:
                    return True
            time.sleep(.01)
        return False
