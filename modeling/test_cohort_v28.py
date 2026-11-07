"""A prior forecast input's outcome is exposed even if not a target ID."""
import unittest,runpy,tempfile,gzip,json
from pathlib import Path
from unittest.mock import patch
class CohortTests(unittest.TestCase):
    def test_previous_numeric_history_ids_are_excluded_from_new_confirmation(self):
        fn=runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/v28-nba-rotation.py'))['blocked']
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'docs/research';folder.mkdir(parents=True)
            (folder/'V27_PROSPECTIVE_R1.json.gz').write_bytes(gzip.compress(json.dumps({'games':[{'sport':'NBA','eventId':'555','inputGameIds':{'1':['123'],'2':['124']}}]}).encode()))
            with patch.dict(fn.__globals__,{'ROOT':root,'protected':lambda:set(),'excluded_validation':lambda:set()}):
                ids=fn();self.assertTrue({'nba:espn:123','nba:espn:124','nba:espn:555'}<=ids)
