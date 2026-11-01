"""SYNTHETIC archive transport tests; no R2/Atlas cloud access is implied."""
import hashlib
import io
import json
import os
import unittest
from unittest.mock import patch, MagicMock
from .artifact_archive import archive_replay_input, NoRedirect
from .storage_summary import canonical, CorrelationSummary


class ArtifactArchiveTests(unittest.TestCase):
    def test_disabled_archival_makes_no_network_request(self):
        with patch.dict(os.environ, {'GRIDIRON_ARCHIVE_MODEL_ARTIFACTS': '0'}), patch('urllib.request.build_opener') as opener:
            result = {'runManifest': {}}
            self.assertIs(archive_replay_input(result, {'rows': []}, 'NFL'), result)
            opener.assert_not_called()

    def test_verified_receipt_matches_the_exact_input_bytes(self):
        model = {'version': 'SYNTHETIC', 'rows': [{'o': 'SYNTH-A', 'd': 'SYNTH-B', 'game': 'SYNTHETIC', 'yards': 1.0}]}
        raw = canonical(model)
        reference = {'version': 1, 'backend': 'r2', 'key': 'artifacts/NFL/'+'a'*64+'.gz', 'sha256': 'a'*64,
                     'rawSha256': hashlib.sha256(raw).hexdigest(), 'rawBytes': len(raw), 'bytes': 80, 'retention': 'protected'}
        response = MagicMock();response.__enter__.return_value = io.BytesIO(json.dumps({'saved': True, 'reference': reference}).encode())
        opener = MagicMock();opener.open.return_value = response
        with patch.dict(os.environ, {'GRIDIRON_ARCHIVE_MODEL_ARTIFACTS': '1', 'APP_URL': 'https://synthetic.example', 'SIMULATION_SERVICE_TOKEN': 'SYNTHETIC-PRIVATE-SERVICE-TOKEN-123456789'}), patch('urllib.request.build_opener', return_value=opener):
            result = archive_replay_input({'runManifest': {}}, model, 'NFL')
            self.assertEqual(result['runManifest']['inputArchive']['status'], 'verified')
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url, 'https://synthetic.example/api/internal/storage/artifact')

    def test_bad_receipt_is_never_called_saved_and_private_auth_never_redirects(self):
        response = MagicMock();response.__enter__.return_value = io.BytesIO(b'{"saved":true,"reference":{}}')
        opener = MagicMock();opener.open.return_value = response
        with patch.dict(os.environ, {'GRIDIRON_ARCHIVE_MODEL_ARTIFACTS': '1', 'APP_URL': 'https://synthetic.example', 'SIMULATION_SERVICE_TOKEN': 'SYNTHETIC-PRIVATE-SERVICE-TOKEN-123456789'}), patch('urllib.request.build_opener', return_value=opener):
            result = archive_replay_input({'runManifest': {}}, {'rows': []}, 'CFB')
            self.assertEqual(result['runManifest']['inputArchive']['status'], 'unavailable')
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example'))

    def test_correlations_use_shared_game_moments_without_retaining_samples(self):
        moments = CorrelationSummary([{'qb': 'SYNTH-QB', 'receiver': 'SYNTH-WR'}])
        for n in range(10000):moments.add([n % 40, n % 40], {'SYNTH-QB': {'passingYards': n % 200}, 'SYNTH-WR': {'receivingYards': n % 200}})
        self.assertEqual(len(moments.moments), 2)
        self.assertTrue(all(v['games'] == 10000 and v['pearson'] == 1 for v in moments.summary()))


if __name__ == '__main__':
    unittest.main()
