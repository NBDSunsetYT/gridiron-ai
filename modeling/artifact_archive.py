"""Optional server-to-server archival of the exact fitted artifact.

Disabled unless explicitly enabled with private R2/account authorization. A failed
archive is recorded as unavailable, never treated as a reproducible saved input.
"""
import gzip
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from .storage_summary import canonical


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def archive_replay_input(result, model, sport):
    if os.environ.get('GRIDIRON_ARCHIVE_MODEL_ARTIFACTS') != '1':
        return result
    receipt = {'status': 'unavailable', 'reason': 'Exact fitted input archival could not be verified.'}
    try:
        base = os.environ.get('APP_URL', '')
        origin = urllib.parse.urlsplit(base)
        secret = os.environ.get('SIMULATION_SERVICE_TOKEN', '')
        if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password or origin.query or origin.fragment or origin.path not in ('', '/') or len(secret) < 32:
            raise ValueError('Private archival configuration is incomplete')
        raw = canonical(model)
        digest = hashlib.sha256(raw).hexdigest()
        compressed = gzip.compress(raw, compresslevel=6, mtime=0)
        if len(raw) > 20_000_000 or len(compressed) > 3_200_000:
            raise ValueError('Artifact exceeds the bounded archival transport')
        request = urllib.request.Request(base.rstrip('/')+'/api/internal/storage/artifact', data=compressed,
            headers={'Authorization': 'Bearer '+secret, 'Content-Type': 'application/gzip',
                     'X-Gridiron-Sport': sport, 'X-Gridiron-Artifact-Sha256': digest}, method='POST')
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=80) as response:
            data = json.loads(response.read(65536))
        reference = data.get('reference', {})
        if (data.get('saved') is not True or reference.get('rawSha256') != digest or reference.get('rawBytes') != len(raw)
                or reference.get('backend') != 'r2' or reference.get('version') != 1 or reference.get('retention') != 'protected'
                or not re.fullmatch(r'[a-f0-9]{64}', reference.get('sha256', ''))
                or reference.get('key') != 'artifacts/'+sport+'/'+reference['sha256']+'.gz'
                or not isinstance(reference.get('bytes'), int) or not 0 < reference['bytes'] <= 200_000_000):
            raise ValueError('Artifact archival receipt failed verification')
        receipt = {'status': 'verified', 'reference': reference, 'sha256': digest,
                   'reason': 'Exact fitted bytes are stored privately. Replay also requires matching code, dependencies and configuration.'}
    except (ValueError, TypeError, AttributeError, KeyError, OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        pass  # Do not log the private service credential, URL error or artifact.
    result['runManifest']['inputArchive'] = receipt
    if receipt['status']=='verified':
        result['runManifest']['exactReplay']={'availableFromThisRecordAlone':False,'artifactReferenceVerified':True,
            'reason':'The referenced fitted input bytes are archived. Replay requires retrieving them and matching code, dependencies, runtime and configuration. Bit-for-bit replay has not been asserted by archival alone.'}
    return result
