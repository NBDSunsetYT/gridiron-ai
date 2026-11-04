import tempfile,unittest
from pathlib import Path
from modeling.audit_storage import snapshot_claim,write_snapshot_once
class AuditStorageTests(unittest.TestCase):
 def test_exclusive_worker_and_crash_safe_reclaim(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'forecast'
   with snapshot_claim(p) as first:
    self.assertTrue(first)
    with snapshot_claim(p) as second:self.assertFalse(second)
   with snapshot_claim(p) as after:self.assertTrue(after)
 def test_completed_snapshot_cannot_be_overwritten(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'frozen.json.gz';self.assertTrue(write_snapshot_once(p,b'original'))
   self.assertFalse(write_snapshot_once(p,b'replacement'));self.assertEqual(p.read_bytes(),b'original');self.assertEqual(list(Path(d).glob('*.partial-*')),[])
