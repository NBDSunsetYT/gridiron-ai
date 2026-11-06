"""Synthetic mechanics only; none of these fixtures are accuracy evidence."""
import unittest,tempfile,os,json,copy
from pathlib import Path
from .overnight_v20.state import Campaign,atomic,alive,process_identity
from .overnight_v20.models import fit_qb_continuity,qb_plans
class LedgerTests(unittest.TestCase):
 def test_restarts_count_only_active_time_and_reserve_interruption(self):
  with tempfile.TemporaryDirectory() as d:
   c=Campaign(d,100,100);c.begin();s=c.heartbeat();self.assertGreaterEqual(s['measuredActiveSeconds'],0);c.end('slice');before=c.state()['measuredActiveSeconds'];c.begin();c.end('complete');self.assertGreaterEqual(c.state()['measuredActiveSeconds'],before);self.assertEqual(len(c.state()['sessions']),2)
 def test_live_identity_and_budget(self):
  self.assertTrue(alive(process_identity(os.getpid())))
  with tempfile.TemporaryDirectory() as d:
   c=Campaign(d,100,1);c.begin();self.assertEqual(c.may_start(2),(False,'cumulative_cpu_budget'));c.end('budget')
 def test_no_duplicate_lease(self):
  with tempfile.TemporaryDirectory() as d:
   c=Campaign(d)
   with c.lease():
    with self.assertRaises(RuntimeError):
     with Campaign(d).lease():pass
 def test_suspended_interval_is_not_claimed_as_active_execution(self):
  with tempfile.TemporaryDirectory() as d:
   c=Campaign(d);c.begin();c.tick-=300;s=c.heartbeat()
   self.assertAlmostEqual(s['measuredActiveSeconds'],5.)
   self.assertGreaterEqual(s['unobservedActiveUpperBoundSeconds'],295.)
   c.end('gap_test')
class FootballTests(unittest.TestCase):
 def test_dynamic_qb_games_conserve_shared_stats(self):
  from .test_engines_v15 import fixture
  from .football_v15 import fit_football
  from .reconstruction_v19.football_fit import enrich
  from .overnight_v20 import football
  from .iterative_learning import digest
  for sport in ['NFL','CFB']:
   rows=fixture(sport);prefix='cfb:fixture:' if sport=='CFB' else 'fixture:'
   for row in rows:
    if row.get('kind')=='pass' and row.get('clock')==3600:row['qb']=row['o']+':qb1'
   m=enrich(fit_football(rows,sport,'2024-02-01T00:00:00Z','SYNTHETIC'),rows,'team_eb_frailty');m['version']=football.VERSION;m['qbContinuity']=fit_qb_continuity(m) if len(m['teams'])>=5 else {'byTeam':{t:{'probabilityRetained':.8} for t in m['teams']},'alpha':4,'beta':1};m['qbPlans']=qb_plans(m,[prefix+'0',prefix+'1'],{});m['sha256']=digest(m);f=football.simulate_football(m,prefix+'0',prefix+'1','2024-02-02T00:00:00Z',1000,20,representative_games=0)
   self.assertTrue(f['quality']['allGamesAccountingReconciled']);self.assertIsNone(f['calibratedProbability']);self.assertEqual(sum(v['count'] for v in f['marginDistribution']['histogram']),1000)
def nba_fixture():
    from datetime import datetime,timezone,timedelta
    games={}
    for day in range(16):
        for pair in range(5):
            gid=f'SYNTHETIC:{day}:{pair}';date=(datetime(2024,1,1,tzinfo=timezone.utc)+timedelta(days=day)).isoformat();teams={};players=[]
            for side in range(2):
                tid=str(2*pair+side);roster=[]
                for i in range(8):
                    made=3+i%3;three=1+i%2;free=1+day%2;p={'athlete_id':int(tid)*10+i,'athlete_display_name':'SYNTHETIC '+tid+' '+str(i),'team_id':tid,'minutes':30.,'starter':i<5,'field_goals_made':made,'field_goals_attempted':10+i%2,'three_point_field_goals_made':three,'three_point_field_goals_attempted':4,'free_throws_made':free,'free_throws_attempted':2,'offensive_rebounds':1,'defensive_rebounds':3,'assists':3,'steals':1,'blocks':1,'turnovers':2,'fouls':3,'points':2*made+three+free};roster.append(p)
                players.extend(roster);t={k:sum(p[k] for p in roster) for k in roster[0] if isinstance(roster[0][k],(float,int)) and k not in ('athlete_id','starter')};t.update(team_score=t['points'],team_home_away='home' if side==0 else 'away',opponent_team_id=str(2*pair+1-side));teams[tid]=t
            games[gid]={'id':gid,'sport':'NBA','at':date,'teams':teams,'players':players,'freeThrowTrips':{t:[2]*8 for t in teams},'stints':[60,120,180]}
    return games

class BasketballTests(unittest.TestCase):
 def test_rebound_hierarchy_and_buzzer_candidates_conserve_games(self):
  from .structural_v18.nba import fit_nba
  from .reconstruction_v19.nba_fit import enrich
  from .overnight_v20.models import enrich_rebounds
  from .overnight_v20.nba import simulate_nba,VERSION
  from .iterative_learning import digest
  games=nba_fixture();m=fit_nba(games,'2024-02-01T00:00:00Z','SYNTHETIC','rotation_bootstrap');m=enrich(m,games,'2024-02-01T00:00:00Z');enrich_rebounds(m,games,m['cutoff']);m['projectedMinutes']={t:{str(p['athlete_id']):30. for p in games['SYNTHETIC:15:0']['players'] if p['team_id']==t} for t in ['0','1']};m['version']=VERSION
  for variant in ['buzzer','share_buzzer']:
   m['reboundVariant']=variant;m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});a=simulate_nba(m,'0','1','2024-02-02T00:00:00Z',1000,20020);b=simulate_nba(m,'0','1','2024-02-02T00:00:00Z',1000,20020)
   self.assertEqual(a['scoreDistributions'],b['scoreDistributions']);self.assertEqual(a['players'],b['players']);self.assertTrue(a['quality']['minutesReconciled']);self.assertTrue(a['quality']['combinedStatsShareOutcomes']);self.assertFalse(a['reboundsAfterPeriodEndAllowed']);self.assertIsNone(a['calibratedProbability'])
   for p,z in a['players'].items():
    self.assertLessEqual(z['fieldGoalsMade']['mean'],z['fieldGoalAttempts']['mean']+1e-9);self.assertLessEqual(z['threePointersMade']['mean'],z['threePointAttempts']['mean']+1e-9);self.assertAlmostEqual(z['pointsReboundsAssists']['mean'],sum(z[k]['mean'] for k in ['points','rebounds','assists']),places=8)

class LeakageTests(unittest.TestCase):
 def test_current_and_future_boxes_do_not_change_pregame_features(self):
  from .overnight_v20.data import features_for,BASKETBALL,FOOTBALL
  from collections import defaultdict
  for sport,stats in [('NFL',FOOTBALL),('CFB',FOOTBALL),('NBA',BASKETBALL)]:
   hist=defaultdict(list)
   for day in range(1,7):
    g={'id':str(day),'at':f'2024-01-{day:02d}T00:00:00Z','end':f'2024-01-{day:02d}T03:00:00Z','home':'a','away':'b','season':2024,'teams':{}}
    for t,o in [('a','b'),('b','a')]:
     totals={s:10. for s in (*stats,'score','plays','dropbacks')};g['teams'][t]={'players':{t+'p':{'stats':totals,'starter':True}},'totals':totals,'opponent':o}
    for t in ['a','b']:hist[t].append(g)
   current=copy.deepcopy(g);current.update(id='future',at='2024-01-08T00:00:00Z',end='2024-01-08T03:00:00Z');before=features_for(current,'a',hist,sport)
   for t in ['a','b']:hist[t].append(current)
   current['teams']['a']['totals']={k:99999 for k in current['teams']['a']['totals']};current['teams']['a']['players']={'FUTURE_PLAYER':{'stats':current['teams']['a']['totals'],'starter':True}}
   self.assertEqual(before,features_for(current,'a',hist,sport));self.assertNotIn('FUTURE_PLAYER',{r['player'] for r in before})
if __name__=='__main__':unittest.main()

