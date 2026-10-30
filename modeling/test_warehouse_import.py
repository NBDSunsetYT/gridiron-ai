"""SYNTHETIC schema/transport checks; real NFL import is reported separately."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('warehouse_importer', Path(__file__).parents[1] / 'scripts/import-pbp-supabase.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ROW = 'game_id,play_id,played_at,offense,defense,play_type,down,yards_to_go,yardline_100,passer_id,receiver_id,epa,success\nSYNTHETIC,1,2023-09-08T00:20:01Z,A,B,pass,1,10,75,QB,WR,0.75,1\n'


class FakeREST:
    user_id = 'ee000000-0000-4000-8000-000000000001'
    def __init__(self):
        self.players = []
        self.plays = []
    def select(self, table, **filters):
        return {'nfl_teams': [{'external_id':'A','id':'team-a'},{'external_id':'B','id':'team-b'}], 'nfl_games':[{'id':'game-a'}], 'nfl_players':self.players}[table]
    def insert_ignoring_duplicates(self, table, rows, conflict):
        target = self.players if table == 'nfl_players' else self.plays
        inserted = [r for r in rows if not any(old['external_id'] == r['external_id'] for old in target)]
        target.extend(inserted)
        return inserted


class WarehouseImportTests(unittest.TestCase):
    def test_mapping_actual_provenance_identity_and_retry_without_updates(self):
        client = FakeREST()
        first = module.import_plays(client, ROW, 'SYNTHETIC MECHANICAL SOURCE', chunk_size=1)
        second = module.import_plays(client, ROW, 'SYNTHETIC MECHANICAL SOURCE', chunk_size=1)
        self.assertEqual(first['insertedPlays'], 1)
        self.assertEqual(second['insertedPlays'], 0)
        self.assertEqual(second['existingPlaysRetained'], 1)
        self.assertIsNone(client.plays[0]['available_at'])
        self.assertEqual(client.plays[0]['epa'], .75)
        self.assertTrue(client.plays[0]['success'])
        self.assertEqual(client.players[0]['name'], 'Name unavailable')
        self.assertTrue(client.plays[0]['version'])
    def test_dry_run_performs_no_insert_and_missing_numbers_stay_missing(self):
        client = FakeREST()
        report = module.import_plays(client, ROW.replace('0.75,1', ','), 'SYNTHETIC', dry_run=True)
        self.assertEqual(report['status'], 'dry_run')
        self.assertEqual(client.plays, [])
        self.assertEqual(client.players, [])
    def test_unavailable_game_and_invalid_evidence_fail_before_mutation(self):
        client = FakeREST()
        with self.assertRaises(ValueError):
            module.import_plays(client, ROW.replace('2023-09-08T00:20:01Z','not-a-time'), 'SYNTHETIC')
        with self.assertRaises(ValueError):
            module.import_plays(client, ROW, 'SYNTHETIC', chunk_size=501)
        unavailable = ROW.replace('epa,success\n', 'epa,success,available_at\n').replace(',0.75,1\n', ',0.75,1,2022-01-01T00:00:00Z\n')
        with self.assertRaisesRegex(ValueError, 'before it occurred'):
            module.import_plays(client, unavailable, 'SYNTHETIC')
        self.assertEqual(client.plays, [])
        self.assertEqual(client.players, [])


if __name__ == '__main__':
    unittest.main()
