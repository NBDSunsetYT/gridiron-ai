"""Source-admission checks with synthetic parquet; no historical accuracy claim."""
import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
import pyarrow as pa
import pyarrow.parquet as pq
from .dynamic_v24.completion.additional_data import recent_nba_packets

class RecentSeasonTests(unittest.TestCase):
    def files(self,folder,corrupt=False):
        players=[];teams=[]
        for tid,other,side in [(1,2,'home'),(2,1,'away')]:
            stats={'field_goals_attempted':2,'field_goals_made':1,'three_point_field_goals_attempted':0,'three_point_field_goals_made':0,'free_throws_attempted':0,'free_throws_made':0}
            for i in range(6):players.append({'game_id':1,'team_id':tid,'athlete_id':tid*10+i,'athlete_display_name':f'Synthetic {tid}-{i}','athlete_position_abbreviation':'G','minutes':40.,'starter':i<5,'did_not_play':False,'points':2,**stats})
            teams.append({'game_id':1,'team_id':tid,'opponent_team_id':other,'team_home_away':side,'game_date_time':datetime(2026,10,20,tzinfo=timezone.utc),'team_score':13 if corrupt and tid==1 else 12,**{k:v*6 for k,v in stats.items()}})
        for k,rows in [('player',players),('team',teams)]:pq.write_table(pa.Table.from_pylist(rows),folder/f'NBA-{k}_box_2027.parquet')
    def test_missing_season_is_explicit_opt_in_and_source_is_hashed(self):
        with tempfile.TemporaryDirectory() as d,patch('modeling.dynamic_v24.completion.additional_data.protected',return_value=set()):
            root=Path(d);self.files(root);g,m=recent_nba_packets(source_folder=root)
            self.assertEqual(len(g),1);self.assertEqual(g[0]['home'],'1');self.assertEqual(len(m['sourceVersions']),2);self.assertFalse(m['originalHistoricalPublicationVerified']);self.assertIs(g[0]['teams']['1']['players']['10']['starter'],True)
    def test_protected_game_filtered_before_materialization(self):
        with tempfile.TemporaryDirectory() as d,patch('modeling.dynamic_v24.completion.additional_data.protected',return_value={'nba:espn:1'}):
            root=Path(d);self.files(root);g,m=recent_nba_packets(source_folder=root);self.assertEqual(g,[])
    def test_conflicting_player_team_scoring_is_quarantined(self):
        with tempfile.TemporaryDirectory() as d,patch('modeling.dynamic_v24.completion.additional_data.protected',return_value=set()):
            root=Path(d);self.files(root,True);g,m=recent_nba_packets(source_folder=root);self.assertEqual(g,[]);self.assertEqual(len(m['rejected']),1)
