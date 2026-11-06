"""Reproduction safeguards; synthetic fixtures are not forecasting evidence."""
import importlib.util
import hashlib
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('v25_recon',Path(__file__).resolve().parents[1]/'scripts/recon-accuracy-v25.py')
recon=importlib.util.module_from_spec(spec)
spec.loader.exec_module(recon)


class BaselineReproductionGuards(unittest.TestCase):
    def test_missing_preflight_stops_numerical_work(self):
        for value in (None,{'failures':[{'reason':'missing'}]}):
            with self.assertRaises(ValueError):recon.validate_preflight(value)

    def test_changed_and_missing_artifacts_are_rejected(self):
        previous=recon.ROOT
        with tempfile.TemporaryDirectory() as folder:
            try:
                recon.ROOT=Path(folder);path=recon.ROOT/'owned.fixture';path.write_bytes(b'SYNTHETIC')
                preflight={'failures':[],'files':{'owned.fixture':hashlib.sha256(path.read_bytes()).hexdigest()}}
                recon.validate_preflight(preflight);path.write_bytes(b'CHANGED')
                with self.assertRaises(ValueError):recon.validate_preflight(preflight)
                path.unlink()
                with self.assertRaises(ValueError):recon.validate_preflight(preflight)
            finally:recon.ROOT=previous

    def test_baseline_drift_is_never_relabelled_as_a_success(self):
        before={'pointForecast':[1.,2.],'seed':240241}
        recon.same_baseline(before,dict(before))
        with self.assertRaises(ValueError):recon.same_baseline(before,{'pointForecast':[1.,2.01],'seed':240241})


if __name__=='__main__':unittest.main()
