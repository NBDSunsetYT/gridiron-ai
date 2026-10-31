"""SYNTHETIC bounded source-normalization tests, not real CFB predictions."""
import csv
import io
import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from .cfb_public_research import (COLUMNS,normalize_public_cfb,prepare_cfb_public,
                                 CFBSourceUnavailable)
from .service import app


def source_row(**changes):
    row={key:None for key in COLUMNS}
    row.update(season=2024,game_id=1000,id=1,pos_team_id=10,def_pos_team_id=20,
               pos_team='SYNTHETIC A',def_pos_team='SYNTHETIC B',wallclock='2024-01-01T12:00:00Z',
               status_type_completed=True,period=1,down=1,distance=10,
               **{'start.yardsToEndzone':70,'start.adj_TimeSecsRem':3200,'end.adj_TimeSecsRem':3170,
                  'start.pos_score_diff':0,'type.text':'Pass Reception','drive.id':'10001',
                  'end.pos_team.id':10,'end.yard':60})
    row.update(passer_player_id=101,passer_player_name='SYNTHETIC QB',receiver_player_id=102,
               receiver_player_name='SYNTHETIC Receiver',completion=True,pass_attempt=True,
               yds_receiving=10,statYardage=10,xp_attempt=False,xp_made=False,
               defensive_two_point_conv=False,fg_made=False,fg_attempt=False,sack=False,
               offense_score_play=False,defense_score_play=False,td_play=False,
               **{'int':False,'pos_fumble_lost':False,'punt':False,'rush':False,'kneel_down':False,
                  'penalty_no_play':False,'penalty_negated_play':False,'penalty_flag':False})
    row.update(changes);return row


class CFBSourceTests(unittest.TestCase):
    def normalize(self,rows):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'SYNTHETIC.parquet';pq.write_table(pa.Table.from_pylist(rows),path)
            return normalize_public_cfb(path,'10','20','2024-01-03T00:00:00Z')

    def test_actual_participant_fields_and_stopped_clock_are_preserved(self):
        raw=source_row(**{'end.adj_TimeSecsRem':3200})
        result=self.normalize([raw]);rows=list(csv.DictReader(io.StringIO(result['csv'])))
        self.assertEqual(rows[0]['sport'],'CFB');self.assertEqual(rows[0]['passer_id'],'cfb:espn:101')
        self.assertEqual(rows[0]['receiver_id'],'cfb:espn:102');self.assertEqual(rows[0]['elapsed_seconds'],'0')
        self.assertEqual(result['playerCatalog'][0]['name'],'SYNTHETIC QB')
        self.assertIsNone(result['playerCatalog'][0]['position'])

    def test_missing_player_identity_is_not_parsed_or_guessed_from_names(self):
        missing=source_row(id=2,passer_player_id=None)
        result=self.normalize([source_row(),missing]);rows=list(csv.DictReader(io.StringIO(result['csv'])))
        self.assertEqual(len(rows),1)
        self.assertEqual(result['counts']['unsupported_event_or_participant_coverage'],1)

    def test_unknown_air_yards_do_not_drop_verified_interception(self):
        interception=source_row(receiver_player_id=None,completion=False,air_yards=None,
                                **{'int':True,'end.pos_team.id':20,'end.yard':30})
        result=self.normalize([interception]);row=list(csv.DictReader(io.StringIO(result['csv'])))[0]
        self.assertEqual(row['interception'],'1');self.assertEqual(row['yards_gained'],'0')
        self.assertEqual(row['turnover_net'],'0');self.assertEqual(result['counts']['accepted_int'],1)

    def test_zero_yard_pass_loss_is_ncaa_rushing_not_a_sack(self):
        source=source_row(receiver_player_id=None,completion=False,pass_attempt=False,
                          sack=True,yds_sacked=0,rusher_player_id=None)
        result=self.normalize([source]);row=list(csv.DictReader(io.StringIO(result['csv'])))[0]
        self.assertEqual(row['play_type'],'rush');self.assertEqual(row['rusher_id'],'cfb:espn:101')
        self.assertEqual(row['yards_gained'],'0')

    def test_incomplete_future_and_negated_plays_never_enter_evidence(self):
        result=self.normalize([source_row(),source_row(id=2,status_type_completed=False),
                               source_row(id=3,wallclock='2024-01-04T00:00:00Z'),
                               source_row(id=4,penalty_negated_play=True)])
        self.assertEqual(result['counts']['accepted_plays'],1)
        self.assertEqual(result['counts']['incomplete_game'],1)
        self.assertEqual(result['counts']['at_or_after_cutoff'],1)
        self.assertEqual(result['counts']['penalty_coverage_excluded'],1)

    def test_mixed_player_and_conversion_events_do_not_duplicate_stats(self):
        result=self.normalize([source_row(xp_attempt=True,xp_made=True,offense_score_play=True,td_play=True,
                                          **{'start.yardsToEndzone':10,'type.text':'Passing Touchdown'})])
        rows=list(csv.DictReader(io.StringIO(result['csv'])))
        self.assertEqual(len(rows),2)
        ordinary=[r for r in rows if r['play_type']=='pass'];tries=[r for r in rows if r['play_type']=='extra_point']
        self.assertEqual(len(ordinary),1);self.assertEqual(len(tries),1)
        self.assertEqual(tries[0]['passer_id'],'');self.assertTrue(tries[0]['play_id'].endswith(':conversion'))
        self.assertEqual(tries[0]['score_diff'],'6')

    def test_defensive_touchdown_conversion_belongs_to_scoring_defense(self):
        event=source_row(receiver_player_id=None,completion=False,defense_score_play=True,
                         td_play=True,xp_attempt=True,xp_made=True,
                         **{'int':True,'end.pos_team.id':20,'end.yard':0,'type.text':'Interception Return Touchdown'})
        result=self.normalize([event]);rows=list(csv.DictReader(io.StringIO(result['csv'])))
        conversion=next(row for row in rows if row['play_type']=='extra_point')
        self.assertEqual(conversion['offense'],'cfb:espn:20')
        self.assertEqual(conversion['defense'],'cfb:espn:10')
        self.assertEqual(conversion['score_diff'],'6')

    def test_current_game_and_source_schema_must_be_verified_before_fetch(self):
        future=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        game={'id':'cfb:espn:1','espnGameId':'1','season':datetime.now(timezone.utc).year,
              'startTime':future,'home':{'id':'cfb:espn:10','espnId':'10'},'away':{'id':'cfb:espn:20','espnId':'20'}}
        with patch('modeling.cfb_public_research.source_file') as fetch:
            for payload in ({'game':{**game,'startTime':'2024-01-01T00:00:00Z'}},
                            {'game':{**game,'home':{'id':'NFL-A','espnId':'10'}}},
                            {'game':game,'csv':'SYNTHETIC client plays'},
                            {'game':game,'simulations':True},
                            {'game':game,'simulations':10000.0}):
                with self.assertRaises(ValueError):prepare_cfb_public(payload)
            fetch.assert_not_called()

    def test_transport_failure_remains_distinct_from_empty_or_insufficient_data(self):
        env={'SIMULATION_SERVICE_TOKEN':'SYNTHETIC-CFB-SERVICE-AUTH-DO-NOT-USE-PROD'}
        with patch.dict(os.environ,env),TestClient(app) as client:
            with patch('modeling.cfb_public_research.prepare_cfb_public',side_effect=CFBSourceUnavailable('SYNTHETIC')):
                response=client.post('/cfb/public/prepare',headers={'Authorization':'Bearer '+env['SIMULATION_SERVICE_TOKEN']},json={'game':{}})
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['detail']['code'],'source_unavailable')
        self.assertEqual(response.headers['retry-after'],'60')


if __name__=='__main__':unittest.main()
