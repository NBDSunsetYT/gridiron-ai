"""Synthetic mechanics/gate tests, never real forecast accuracy evidence."""
import copy,unittest
import numpy as np
from .test_engines_v15 import fixture
from .football_v15 import fit_football,Predictor
from .reconstruction_v19.football_fit import enrich
from .integration_v22.football import mechanics_fixture,simulate_football,VERSION
from .integration_v22.clock import RuntimeClock
from .integration_v22.inputs import completion_offset,CorrectedDropback,anonymous_play_credits
from .integration_v22.gates import audit,required_checks
from .integration_v22.passing import PassingChain
class IntegratedMechanicsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  rows=fixture('CFB')
  for r in rows:
   for key in ['o','d','qb','runner','receiver']:
    if key in r:r[key]=r[key].replace('cfb:fixture:','fixture:')
  m=enrich(fit_football(rows,'CFB','2024-02-01T00:00:00Z','synthetic_fixture_only'),rows,'team_eb');m.update(version=VERSION,syntheticFixture=True,forecastSeason=2024,gameSeasons={r['game']:2024 for r in rows});mass=np.zeros(91);mass[30]=1;m['censoredClock']={'version':'synthetic-clock','metadata':{'fitCutoff':'2024-02-01T00:00:00Z'},'globalMass':mass.tolist(),'pools':[],'supported':['pass','rush','punt','field_goal','kneel','sack'],'administrative':{'verified':True,'sourceVersion':'synthetic-test-only','mass':mass.tolist()},'timingRegimeValidated':False};cls.model=m
 def test_clock_rejects_zero_timed_mass_and_unknown_administration(self):
  a=copy.deepcopy(self.model['censoredClock']);a['globalMass'][30]=0;a['globalMass'][0]=1
  with self.assertRaises(ValueError):RuntimeClock(a,'2024-03-01T00:00:00Z')
  a=copy.deepcopy(self.model['censoredClock']);a['administrative']=None
  with self.assertRaisesRegex(ValueError,'Administrative'):RuntimeClock(a,'2024-03-01T00:00:00Z').cdf('penalty',False,False)
 def test_complete_fixture_games_conserve_time_and_per_team_stats(self):
  r=mechanics_fixture(self.model,'fixture:0','fixture:1','2024-03-01T00:00:00Z',8,22001);self.assertEqual(r['gameEnvironment']['regulationSeconds'],3600);self.assertNotIn('homeWinProbability',r);self.assertEqual(r['historicalGamesEvaluated'],0)
  for t,ss in r['teamDistributions'].items():
   self.assertAlmostEqual(ss['passingYards']['mean'],ss['receivingYards']['mean']);self.assertAlmostEqual(ss['completions']['mean'],ss['receptions']['mean'])
  for i in range(3):
   plays=[p for p in r['representativePlays'] if p['game']==i];self.assertEqual(sum(p['clockCharge'] for p in plays),3600)
   for q in range(1,5):self.assertEqual(sum(p['clockCharge'] for p in plays if p['period']==q),900)
 def test_fixture_replay_is_deterministic(self):
  a=mechanics_fixture(self.model,'fixture:0','fixture:1','2024-03-01T00:00:00Z',4,22001);b=mechanics_fixture(self.model,'fixture:0','fixture:1','2024-03-01T00:00:00Z',4,22001);self.assertEqual(a,b)
 def test_scoring_drive_count_is_not_incremented_by_field_reset(self):
  m=copy.deepcopy(self.model);m['play']['classes']=[1];m['play']['coefficients']=[m['play']['coefficients'][0]];m['play']['coefficients'][0]=[0.]*len(m['play']['coefficients'][0]);m['play']['intercepts']=[0.];m['rushTouchdown']['coefficients']=[[0.]*len(x) for x in m['rushTouchdown']['coefficients']];m['rushTouchdown']['intercepts']=[-30.,30.]
  r=mechanics_fixture(m,'fixture:0','fixture:1','2024-03-01T00:00:00Z',2,22002);self.assertEqual(r['gameEnvironment']['plays'],120);self.assertEqual(r['gameEnvironment']['drives'],120)
 def test_real_forecast_cannot_use_fixture_entry_or_missing_evidence(self):
  m=copy.deepcopy(self.model);m['syntheticFixture']=False
  with self.assertRaises(ValueError):mechanics_fixture(m,'fixture:0','fixture:1','2024-03-01T00:00:00Z')
  match={'id':'fixture:g','home':'fixture:0','away':'fixture:1','at':'2024-03-01T00:00:00Z','cutoff':'2024-02-29T23:30:00Z'}
  with self.assertRaisesRegex(ValueError,'withheld'):simulate_football(m,match,{},None)
 def test_completion_bridge_preserves_sack_interception_and_mass(self):
  p=Predictor(self.model['dropback']);x=np.zeros((25,13));off=np.array(['fixture:0']*25);defense=np.array(['fixture:1']*25);raw=p.probabilities(x,off,defense);q=raw[:,3]/(raw[:,3]+raw[:,2]);shift=completion_offset(q,.55);wrapped=CorrectedDropback(p,{'fixture:0':shift},['fixture:0','fixture:1']);a=wrapped.probabilities(x,off,defense);np.testing.assert_allclose(a[:,:2],raw[:,:2]);np.testing.assert_allclose(a.sum(axis=1),1);self.assertAlmostEqual(np.mean(a[:,3]/(a[:,3]+a[:,2])),.55)
 def test_opportunity_chain_preserves_unassigned_budget_and_rejects_future(self):
  names=['team_passingAttempts','participation3','participation5','passingAttempts_last'];rows=[]
  for i in range(110):
   for pid,attempts,baseline in [('__team__',30,30),('qb1',24,23),('qb2',4,5)]:
    r={'gameId':str(i),'at':'2023-01-01T00:00:00Z','team':'test','player':pid,'stat':'passingAttempts','x':[30,1,1,baseline],'featureNames':names,'baseline':baseline,'y':attempts,'opportunity':attempts};rows.append(r)
    if pid!='__team__':rows.append(r|{'stat':'passingYards','y':attempts*.6*10,'actualAttempts':attempts,'actualCompletions':attempts*.6})
  m=PassingChain().fit(rows,'2023-02-01T00:00:00Z');rs=[r|{'at':'2023-03-01T00:00:00Z'} for r in rows[:5]];p,b=m.predict_team(rs);self.assertGreater(b['unassignedAttempts'],0);self.assertAlmostEqual(sum(v for (pid,s),v in p.items() if s=='passingAttempts')+b['unassignedAttempts'],b['teamAttempts']);self.assertNotIn(('unknown','passingAttempts'),p)
  with self.assertRaisesRegex(ValueError,'Future'):PassingChain().fit(rows,'2022-01-01T00:00:00Z')
 def test_anonymous_play_credit_is_owned_by_team_not_a_shared_fake_qb(self):
  rows=[{'game':'g','o':t,'kind':'pass','qb':'cfb:espn:-1','complete':0,'yards':0} for t in ['home','away']];rows.append(rows[0]|{'game':'future'})
  c=anonymous_play_credits(rows,{'g'});self.assertEqual(c['home']['g']['passingAttempts'],1);self.assertEqual(c['away']['g']['passingAttempts'],1);self.assertNotIn('future',c['home'])
 def test_mutated_model_cannot_reuse_checksum(self):
  m=copy.deepcopy(self.model);m['sha256']='stale';g={'id':'fixture:g','at':'2024-03-01T00:00:00Z','cutoff':'2024-02-29T23:30:00Z'};q=audit(m,g,{},None);self.assertIn('model_content_checksum',q['reasons']);self.assertFalse(q['fullGameSimulationAllowed'])
 def test_timing_evidence_remains_league_specific(self):
  self.assertIn('nfl_timing_regime',required_checks('NFL'));self.assertNotIn('ncaa_timing_regime',required_checks('NFL'));self.assertIn('ncaa_timing_regime',required_checks('CFB'))
  with self.assertRaises(ValueError):required_checks('NBA')
if __name__=='__main__':unittest.main()
