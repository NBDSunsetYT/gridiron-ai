"""Software fixtures and invariant tests, never real forecasting evidence."""
import unittest,tempfile,copy
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import numpy as np
from .dynamic_v24.state import DynamicState
from .dynamic_v24.live import FeedLog,Outbox,player_projection
from .dynamic_v24.registry import Registry,decision
from .dynamic_v24.event_models import EventModel,features
from .dynamic_v24 import football,basketball
from .dynamic_v24.stat_models import StatModel
from .dynamic_v24.stat_data import records
from .dynamic_v24.worker import run_once
from .fullgame_v23.accounting import FootballLedger,FootballPlay,BasketballLedger
from .fullgame_v23.modes import Mode,context
from .test_fullgame_v23 import GeneratedBasketballTests
from .test_engines_v15 import fixture
SOURCE={'source':'https://example.org/software-test-only','sourceVersion':'synthetic-not-real-sports-data'}
def ctx(s):return context(Mode.MECHANICS,s,'v24:software-fixture',[SOURCE])

class StateTests(unittest.TestCase):
 def test_snapshot_is_before_outcome_and_immutable(self):
  s=DynamicState('NFL',['H','A']);a=s.features('H');s.observe({'id':'1','team':'H','kind':'pass','gain':30,'success':True,'points':6});b=s.features('H');self.assertEqual(a[1]['recent_explosives'],0);self.assertEqual(b[1]['recent_explosives'],1);self.assertEqual(a[0]['score_diff'],0)
 def test_duplicate_does_not_change_workload(self):
  s=DynamicState('CFB',['H','A']);e={'id':'1','team':'H','kind':'rush','actor':'r','gain':1};s.observe(e);self.assertFalse(s.observe(e));self.assertEqual(s.players['r']['actions'],1)
 def test_rest_and_minutes_are_from_clock_not_final_box(self):
  s=DynamicState('NBA',['H','A']);s.set_lineup('H',['1','2','3','4','5']);s.set_lineup('A',['11','12','13','14','15']);s.tick(1,660);s.set_lineup('H',['6','2','3','4','5']);s.tick(1,600);self.assertEqual(s.player_seconds['1'],60);self.assertEqual(s.player_seconds['6'],60);self.assertEqual(s.stints['1'],0)
 def test_backward_clock_is_not_silently_accepted(self):
  s=DynamicState('NFL',['H','A']);s.tick(1,700)
  with self.assertRaises(ValueError):s.tick(1,800)
 def test_uncertain_availability_not_healthy_by_default(self):
  s=DynamicState('CFB',['H','A']);self.assertFalse(s.snapshot()['fullPersonnelKnown']);s.unavailable.add('q')
  with self.assertRaises(ValueError):s.observe({'id':'x','team':'H','kind':'pass','actor':'q'})
 def test_variant_b_excludes_momentum_outcomes(self):
  row={'base':{'score_diff':3},'dynamic':{'recent_success':1,'fatigue_stint_square':9}};self.assertNotIn('recent_success',features(row,'B'));self.assertIn('recent_success',features(row,'C'));self.assertNotIn('fatigue_stint_square',features(row,'B_momentum'))

class FeedTests(unittest.TestCase):
 def row(self,n=1,revision=0):return {'sport':'NFL','eventId':'e','id':str(n),'sequence':n,'revision':revision,'sourceTimestamp':'2024-01-01T00:00:00Z','receivedAt':'2024-01-01T00:00:02Z',**SOURCE}
 def test_duplicate_and_correction_preserve_versions(self):
  f=FeedLog('NFL','e');r=self.row();f.ingest(r,now='2024-01-01T00:00:03Z');self.assertFalse(f.ingest(r,now='2024-01-01T00:00:03Z')['recompute']);fixed=r|{'revision':1,'yards':3};self.assertTrue(f.ingest(fixed,now='2024-01-01T00:00:03Z')['requiresRebuild']);self.assertEqual(len(f.versions),2)
 def test_delayed_feed_preserves_last_verified_time(self):
  f=FeedLog('NFL','e');f.ingest(self.row(),now='2024-01-01T00:00:03Z');r=self.row(2)|{'receivedAt':'2024-01-01T00:10:00Z'};self.assertEqual(f.ingest(r,now='2024-01-01T00:10:01Z')['status'],'frozen');self.assertEqual(f.snapshot()['lastVerifiedTimestamp'],'2024-01-01T00:00:00Z')
 def test_gap_cannot_be_healed_by_just_the_next_event(self):
  f=FeedLog('NFL','e');f.ingest(self.row(),replay=True);f.ingest(self.row(3),replay=True);self.assertEqual(f.ingest(self.row(4),replay=True)['reason'],'event_sequence_gap')
 def test_unversioned_change_or_foreign_event_rejected(self):
  f=FeedLog('NFL','e');f.ingest(self.row(),replay=True)
  with self.assertRaises(ValueError):f.ingest(self.row()|{'points':6},replay=True)
  with self.assertRaises(ValueError):f.ingest(self.row(2)|{'eventId':'other'},replay=True)
 def test_verified_threshold_required_and_ties_respect_operator(self):
  with self.assertRaises(ValueError):player_projection(2,[2,3,4],3)
  r=player_projection(2,[2,3,4],3,{'verified':True,'sourceVersion':'test','settlementRules':'test >','operator':'>'});self.assertAlmostEqual(r['probability'],1/3);self.assertEqual(r['remainingMean'],1)

class QueueTests(unittest.TestCase):
 def test_worker_has_actual_timeout_and_never_publishes_late_result(self):
  import time
  key=self.q.enqueue(self.s,'m',qualified=True);r=run_once(self.q,lambda _:time.sleep(.05),maximum_seconds=.01);self.assertEqual(r['status'],'withheld');self.assertIsNone(self.q.cached(key))
 def test_new_snapshot_fences_running_old_job(self):
  self.q.enqueue(self.s,'m',qualified=True,now=0);a=self.q.claim(now=1);self.q.enqueue(self.s|{'version':'b'},'m',qualified=True,now=2)
  with self.assertRaises(ValueError):self.q.finish(a['id'],a['token'],result={},now=3)
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.q=Outbox(Path(self.tmp.name)/'jobs.db');self.s={'eventId':'e','status':'verified_current','version':'a'}
 def tearDown(self):self.q.db.close();self.tmp.cleanup()
 def test_dedup_and_one_lease(self):
  a=self.q.enqueue(self.s,'m',qualified=True,now=0);b=self.q.enqueue(self.s,'m',qualified=True,now=0);self.assertEqual(a,b);j=self.q.claim(now=1);self.assertIsNone(self.q.claim(now=1));self.q.finish(j['id'],j['token'],result={'value':1},now=2);self.assertEqual(self.q.cached(a),{'value':1})
 def test_fencing_expired_workers(self):
  self.q.enqueue(self.s,'m',qualified=True,now=0);a=self.q.claim(now=1,lease_seconds=2);self.q.claim(now=4);b=self.q.claim(now=7)
  with self.assertRaises(ValueError):self.q.finish(a['id'],a['token'],result={},now=8)
  self.q.finish(b['id'],b['token'],result={},now=8)
 def test_quota_and_unqualified_job(self):
  with self.assertRaises(ValueError):self.q.enqueue(self.s,'m')
  self.assertTrue(self.q.provider_request('p',now=0,daily_limit=1));self.assertFalse(self.q.provider_request('p',now=100,daily_limit=1));self.assertTrue(self.q.provider_request('p',now=86400,daily_limit=1))
 def test_retry_backoff_and_obsolete_queue(self):
  self.q.enqueue(self.s,'m',qualified=True,now=0);a=self.q.claim(now=1);self.q.finish(a['id'],a['token'],error='temporary',now=2);self.assertIsNone(self.q.claim(now=3));self.q.enqueue(self.s|{'version':'b'},'m',qualified=True,now=4);self.assertEqual(self.q.db.execute("SELECT status FROM jobs WHERE id=?",(a['id'],)).fetchone()[0],'obsolete')

class RemainingGameTests(unittest.TestCase):
 def test_dynamic_basketball_preserves_actor_when_defense_rebounds(self):
  from .dynamic_v24.policy import BasketballPolicy
  class Model:
   classes=['turnover','two','three','free_throws']
   def predict(self,rows):return np.tile([.1,.5,.3,.1],(len(rows),1)) # explicit software fixture
  game=GeneratedBasketballTests().game();policy=BasketballPolicy(list(game['teams']),Model(),{'conditionalEventLawAccepted':True});r=basketball._complete_games(game,ctx('NBA'),2,24024,[4,8,12],policy=policy);self.assertTrue(r['mechanicalInvariantsPassed'])
 def football_kernel(self,sport):
  rows=fixture(sport);teams=sorted({r['o'] for r in rows})[:2];rows=[r for r in rows if r['o'] in teams]
  for r in rows:r['complete']=int(r['kind']=='pass' and r['complete'] and not r['int']);r['int']=int(r['kind']=='pass' and r['int'])
  owners={p:r['o'] for r in rows for p in [r.get('qb'),r.get('runner'),r.get('receiver')] if p};return football.PlayKernel(sport,teams,rows,owners)
 def test_football_only_remaining_clock_and_past_stats_retained(self):
  for sport in ['NFL','CFB']:
   k=self.football_kernel(sport);ledger=FootballLedger(sport,k.teams,k.owners);team=k.teams[0];q=next(p for p,t in k.owners.items() if t==team);ledger.apply(FootballPlay('pass',team,quarterback=q));initial={'ledger':ledger,'period':4,'remaining':60,'offense':team,'firstReceivingTeam':team,'field':75,'down':1,'distance':10,'warningTaken':True};result=football.remaining_games(k,ctx(sport),2024,initial,2,24024,{'extra_point':[1],'two_point':[0,1]})
   for r in result['results']:self.assertEqual(r['simulatedRemainingRegulationSeconds'],60);self.assertEqual(r['actualRegulationSeconds'],3540);self.assertGreaterEqual(r['team'][team]['passingAttempts'],1)
 def test_basketball_remaining_only_keeps_actual_points(self):
  game=GeneratedBasketballTests().game();teams=list(game['teams']);owners={str(p['athlete_id']):p['team_id'] for p in game['players']};ledger=BasketballLedger(teams,owners)
  for t in teams:ledger.set_lineup(t,[p for p,own in owners.items() if own==t][:5])
  for _ in range(3):ledger.tick(720)
  ledger.tick(660);ledger.shot('H','1',3,True,assist='2');ledger.verify(2820);initial={'ledger':ledger,'period':4,'remaining':60,'offense':'A','firstPossessionTeam':'H','shotClock':24};r=basketball.remaining_games(game,ctx('NBA'),initial,2,24024,[4,8,12])
  for row in r['results']:self.assertGreaterEqual(row['scores']['H'],3);self.assertEqual(row['actualSeconds'],2820);self.assertEqual(row['simulatedRemainingSeconds'],60+300*row['overtimePeriods'])

class RegistryTests(unittest.TestCase):
 def test_quantile_median_is_not_labeled_a_conditional_mean(self):
  self.assertEqual(StatModel('quantile','receivingTouchdowns').estimand,'conditional_median');self.assertEqual(StatModel('opponent_ridge','receivingYards').estimand,'conditional_mean')
 def test_single_window_or_interval_regression_never_qualifies(self):
  self.assertFalse(decision([{'games':100,'deltaCIAdjusted':[-2,-1]}])['accepted']);w={'games':100,'deltaCIAdjusted':[-2,-1],'intervalCoverageRegression':.2};self.assertFalse(decision([w,w])['accepted'])
 def test_no_production_promotion_and_append_only_versions(self):
  with tempfile.TemporaryDirectory() as tmp:
   reg=Registry(Path(tmp)/'models.json')
   with self.assertRaises(ValueError):reg.register({'productionPromotion':True})
   r={'sport':'NFL','stat':'passingYards','accepted':True,'productionPromotion':False};a=reg.register(r);self.assertEqual(reg.register(r),a);b=reg.register(r|{'family':'other'});self.assertNotEqual(a,b)

class TemporalIntegrityTests(unittest.TestCase):
 def test_current_or_future_outcomes_do_not_change_the_feature_vector(self):
  from datetime import timedelta
  gs=[]
  for day in range(12):
   at=(datetime(2024,1,1,tzinfo=timezone.utc)+timedelta(days=3*day)).isoformat();teams={t:{'players':{'p'+t:{'stats':{'minutes':30.,'rebounds':float(day+2)},'position':'C'}},'totals':{'score':100+day},'opponent':'A' if t=='H' else 'H'} for t in ['H','A']};gs.append({'id':str(day),'sport':'NBA','at':at,'season':2024,'home':'H','away':'A','teams':teams})
  before=[r for r in records(gs,'NBA') if r['gameId']=='11'];altered=copy.deepcopy(gs);altered[-1]['teams']['H']['players']['pH']['stats']['rebounds']=999;altered[-1]['teams']['H']['totals']['score']=999;after=[r for r in records(altered,'NBA') if r['gameId']=='11'];self.assertEqual([r['x'] for r in before],[r['x'] for r in after]);self.assertNotEqual([r['y'] for r in before],[r['y'] for r in after])
