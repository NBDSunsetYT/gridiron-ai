import unittest,importlib.util
from pathlib import Path
from .overnight_v20.state import digest
from .accuracy_v20.quality import aware
spec=importlib.util.spec_from_file_location('v26_grader_test',Path(__file__).resolve().parents[1]/'scripts/v26-grade.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ProspectiveGrading(unittest.TestCase):
    def test_future_games_are_not_requested_as_final_results(self):
        g={'forecastCapturedAt':'2026-11-06T23:00:00Z','eventAt':'2026-11-07T00:00:00Z'}
        self.assertFalse(module.due(g,aware('2026-11-06T23:30:00Z')))
        self.assertFalse(module.due(g,aware('2026-11-07T02:00:00Z')))
        self.assertTrue(module.due(g,aware('2026-11-07T04:00:00Z')))
    def test_backdated_or_mutated_predictions_fail(self):
        g={'forecastCapturedAt':'2026-11-07T00:00:00Z','eventAt':'2026-11-07T00:00:00Z'}
        with self.assertRaises(ValueError):module.due(g,aware('2026-11-08T00:00:00Z'))
        g['forecastCapturedAt']='2026-11-06T23:00:00Z';g['predictionHash']=digest(g);s={'games':[g]};s['sha256']=digest(s);module.verify_snapshot(s)
        g['eventAt']='2026-11-09T00:00:00Z'
        with self.assertRaises(ValueError):module.verify_snapshot(s)
    def test_published_snapshots_verify_without_loading_target_outcomes(self):
        import json,gzip
        root=Path(__file__).resolve().parents[1]
        for rev in ('R1','R2'):module.verify_snapshot(json.loads(gzip.decompress((root/'docs/research'/('V26_PROSPECTIVE_'+rev+'.json.gz')).read_bytes())))


if __name__=='__main__':unittest.main()
