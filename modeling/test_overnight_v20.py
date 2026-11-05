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
if __name__=='__main__':unittest.main()
