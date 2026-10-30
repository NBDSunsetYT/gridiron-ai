"""Synthetic schema fixtures; real historical audit is reported separately."""
import csv
import io
import unittest
from modeling.nflverse_adapter import normalize


class AdapterTests(unittest.TestCase):
    def fixture(self):
        row = {'season_type':'REG','week':'1','game_id':'SYNTH','play_id':'1','posteam':'A','defteam':'B','play_type':'run',
               'game_half':'Half1','game_seconds_remaining':'3570','down':'1','ydstogo':'10','yardline_100':'75',
               'time_of_day':'2023-09-10T17:03:52Z','fixed_drive':'1','rusher_player_id':'RB','yards_gained':'5'}
        return row

    def test_actual_run_mapping_and_clock(self):
        row = self.fixture()
        nxt = {**row, 'play_id':'2','game_seconds_remaining':'3530'}
        text, report = normalize([row,nxt])
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(rows[0]['play_type'], 'rush')
        self.assertEqual(rows[0]['elapsed_seconds'], '40')
        self.assertEqual(rows[0]['played_at'], row['time_of_day'])
        self.assertEqual(rows[0]['availability'], '{}')
        self.assertEqual(report['excluded']['unknown_or_extreme_clock_duration'], 1)

    def test_future_week_and_missing_timestamp_not_filled(self):
        row = self.fixture()
        _, report = normalize([{**row,'time_of_day':''},{**row,'week':'13'}], max_week=12)
        self.assertEqual(report['normalizedPlays'], 0)
        self.assertEqual(report['excluded']['missing_actual_timestamp'], 1)
        self.assertEqual(report['excluded']['outside_training_window'], 1)
