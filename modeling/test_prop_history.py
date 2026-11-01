"""Synthetic mechanics fixtures only; not production validation evidence."""
import unittest
from datetime import datetime,timezone
from .prop_history import nfl_history,summarize

class Dataset:
    metadata={'url':'https://synthetic.invalid/fixture','checkedAt':'2026-11-01T00:00:00Z'}
    def __init__(self,rows):self.values=rows
    def rows(self):return iter(self.values)

class PropHistoryTests(unittest.TestCase):
    def inputs(self):
        roster=[{'gsis_id':'SYNTHETIC-PLAYER','team':'BAL','week':'9','status':'ACT','espn_id':'123','full_name':'SYNTHETIC'}, {'gsis_id':'SYNTHETIC-AWAY','team':'BUF','week':'9','status':'ACT'}]
        stats=[{'player_id':'SYNTHETIC-PLAYER','team':'BAL','season_type':'REG','week':str(w),'game_id':'SYNTHETIC-'+str(w),'receiving_yards':str(w*10),'receptions':'2'} for w in range(1,9)]
        values={'rosters':Dataset(roster),'player_stats':Dataset(stats),'injuries':Dataset([])}
        return {'game':{'id':'SYNTHETIC','home':'BAL','away':'BUF','season':2026,'week':9,'startTime':'2026-11-05T00:00:00Z'}},values
    def run_history(self,data,values):return nfl_history(data,lambda kind,season:values[kind],datetime(2026,11,1,tzinfo=timezone.utc))
    def test_published_totals_are_not_simulated_games(self):
        data,values=self.inputs();r=self.run_history(data,values);d=r['players']['SYNTHETIC-PLAYER']['receivingYards']
        self.assertEqual(d['sampleSize'],8);self.assertEqual(sum(b['count'] for b in d['histogram']),8);self.assertNotIn('simulations',r);self.assertFalse(r['calibrated'])
        self.assertNotIn('passingYards',r['players']['SYNTHETIC-PLAYER'])
    def test_future_stats_other_teams_and_absent_games_not_silently_joined(self):
        data,values=self.inputs();before=self.run_history(data,values)['inputVersion'];values['player_stats'].values.extend([{'player_id':'SYNTHETIC-PLAYER','team':'BAL','season_type':'REG','week':'9','receiving_yards':'999'},{'player_id':'SYNTHETIC-PLAYER','team':'KC','season_type':'REG','week':'8','receiving_yards':'999'}]);self.assertEqual(before,self.run_history(data,values)['inputVersion'])
    def test_uncertain_player_not_assumed_active(self):
        data,values=self.inputs();values['injuries']=Dataset([{'team':'BAL','week':'9','gsis_id':'SYNTHETIC-PLAYER','report_status':'Questionable'}]);r=self.run_history(data,values);self.assertNotIn('SYNTHETIC-PLAYER',r['players']);self.assertIn('SYNTHETIC-PLAYER',r['withheldPlayers'])
    def test_insufficient_or_stale_roster_not_filled(self):
        data,values=self.inputs();values['player_stats'].values=values['player_stats'].values[-4:];self.assertEqual(self.run_history(data,values)['players'],{})
        values['rosters'].values[1]['week']='1'
        with self.assertRaisesRegex(ValueError,'roster'):self.run_history(data,values)
    def test_conflicting_source_duplicates_rejected(self):
        data,values=self.inputs();values['player_stats'].values.append({**values['player_stats'].values[0],'receiving_yards':'999'})
        with self.assertRaisesRegex(ValueError,'Conflicting'):self.run_history(data,values)
    def test_histograms_capped_at_twelve_and_no_unknown_zeros(self):
        logs=[{'id':str(i),'values':{'receivingYards':i}} for i in range(20)];d=summarize(logs);self.assertEqual(d['receivingYards']['sampleSize'],12);self.assertNotIn('passingYards',d)

if __name__=='__main__':unittest.main()

class CollegeHistoryTests(unittest.TestCase):
    def test_actual_stat_event_aggregation_includes_overtime_sacks_and_excludes_tries(self):
        import json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from datetime import timedelta
        import pyarrow as pa
        import pyarrow.parquet as pq
        from .prop_history import cfb_history
        rows=[];now=datetime.now(timezone.utc)
        for i in range(6):
            base={'game_id':100+i,'pos_team_id':1,'status_type_completed':True,'wallclock':(now-timedelta(days=i+1)).isoformat(),'passer_player_id':10,'receiver_player_id':20,'rusher_player_id':30,'passer_player_name':'SYNTHETIC QB','receiver_player_name':'SYNTHETIC WR','rusher_player_name':'SYNTHETIC RB','pass_attempt':False,'sack':False,'rush':False,'completion':False,'int':False,'yds_receiving':0,'yds_rushed':0,'yds_sacked':-3,'xp_attempt':False,'two_point_conv_result':None,'penalty_no_play':False,'penalty_negated_play':False,'offense_score_play':False,'td_play':False}
            rows.extend([{**base,'pass_attempt':True,'completion':True,'yds_receiving':10},{**base,'pass_attempt':True,'completion':True,'yds_receiving':20,'offense_score_play':True,'td_play':True},{**base,'rush':True,'yds_rushed':5},{**base,'sack':True},{**base,'pass_attempt':True,'completion':True,'yds_receiving':2,'two_point_conv_result':'success'}])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'SYNTHETIC.parquet';pq.write_table(pa.Table.from_pylist(rows),path)
            game={'id':'cfb:espn:999','espnGameId':'999','status':'scheduled','season':2026,'startTime':(now+timedelta(days=2)).isoformat(),'home':{'id':'cfb:espn:1','espnId':'1'},'away':{'id':'cfb:espn:2','espnId':'2'}}
            source={'path':str(path),'sha256':'SYNTHETIC','url':'https://synthetic.invalid','collectedAt':now.isoformat()}
            with patch('modeling.cfb_public_research._prepare_cfb_public',return_value={'game':game}),patch('modeling.cfb_public_research.source_file',return_value=source):r=cfb_history({'game':game})
            self.assertEqual(r['players']['cfb:espn:10']['passingYards']['histogram'],[{'value':30.0,'count':6}]);self.assertEqual(r['players']['cfb:espn:20']['receivingYards']['histogram'],[{'value':30.0,'count':6}]);self.assertEqual(r['players']['cfb:espn:10']['rushingYards']['histogram'],[{'value':-3.0,'count':6}]);self.assertNotIn('simulations',r)
