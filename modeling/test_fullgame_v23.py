"""Synthetic software invariants; no fixture is historical accuracy evidence."""
import copy,unittest,importlib.util
import numpy as np
from .fullgame_v23.accounting import FootballLedger,FootballPlay,BasketballLedger,team_actor
from .fullgame_v23.rules import RegulationClock,FootballOvertime,dead_ball_enforcement,runoff_seconds,try_required
from .fullgame_v23.modes import Mode,context,label
from .fullgame_v23.forecast import qualify,compact
from .fullgame_v23.ordering import canonical_order
from .fullgame_v23.gamebook import primary_actions,reconcile
from .fullgame_v23.football import PlayKernel,mechanics_games as football_games,restart_field,touchback_field
from .fullgame_v23.clock_phases import PhaseClockLaw,nfl_stopped_live_pairs
from .fullgame_v23.replay import ordered_rows,clock_audit
from .fullgame_v23.basketball import mechanics_games as basketball_games
from .test_engines_v15 import fixture
from .overnight_v20.state import digest
SOURCE={'source':'https://example.org/synthetic-software-fixture','sourceVersion':'explicit_fixture_not_real_sports_data'}
def ctx(s):return context(Mode.MECHANICS,s,'fixture:v23',[SOURCE])
class AccountingTests(unittest.TestCase):
 def setUp(self):self.owners={'q':'H','r':'H','b':'H','other':'A'}
 def test_shared_pass_updates_correlated_statistics(self):
  l=FootballLedger('NFL',['H','A'],self.owners);l.apply(FootballPlay('pass','H',12,'q','r',complete=True));self.assertEqual(l.players['q']['passingYards'],l.players['r']['receivingYards']);self.assertEqual(l.team['H']['completions'],1);self.assertTrue(l.verify())
 def test_league_sack_accounting_differs(self):
  for sport,carries in [('NFL',0),('CFB',1)]:
   l=FootballLedger(sport,['H','A'],self.owners);l.apply(FootballPlay('sack','H',-8,'q'));l.verify();self.assertEqual(l.team['H']['carries'],carries);self.assertEqual(l.team['H']['netPassingYards'],-8 if sport=='NFL' else 0)
 def test_ncaa_clock_stoppers_are_team_credits(self):
  l=FootballLedger('CFB',['H','A'],self.owners);l.apply(FootballPlay('kneel','H',-2,runner='q'));l.apply(FootballPlay('spike','H',quarterback='q'));l.verify();self.assertEqual(l.players['q']['carries'],0);self.assertEqual(l.players[team_actor('H')]['carries'],1);self.assertEqual(l.players[team_actor('H')]['passingAttempts'],1)
 def test_anonymous_pass_remains_team_credit(self):
  l=FootballLedger('CFB',['H','A'],self.owners);l.apply(FootballPlay('pass','H'));l.verify();self.assertEqual(l.players[team_actor('H')]['passingAttempts'],1);self.assertEqual(l.players['q']['passingAttempts'],0)
 def test_penalty_nullification_preserves_accounting(self):
  l=FootballLedger('NFL',['H','A'],self.owners);l.apply(FootballPlay('pass','H',30,'q','r',complete=True,no_play=True,accepted_penalty=True,penalty_team='H',penalty_yards=10));self.assertEqual(l.team['H']['passingAttempts'],0);self.assertEqual(l.team['H']['penaltyYards'],10);l.verify()
 def test_live_play_penalty_can_retain_counting_stats(self):
  l=FootballLedger('CFB',['H','A'],self.owners);l.apply(FootballPlay('rush','H',19,runner='b',accepted_penalty=True,penalty_team='H',penalty_yards=10));self.assertEqual(l.team['H']['rushingYards'],19);l.verify()
 def test_lateral_yards_reconcile_without_an_extra_catch(self):
  l=FootballLedger('NFL',['H','A'],self.owners);l.apply(FootballPlay('pass','H',20,'q','r',complete=True,receiving_credits=(('r',7),('b',13))));l.verify();self.assertEqual(l.players['b']['receptions'],0);self.assertEqual(l.team['H']['receptions'],1)
 def test_invalid_events_are_rejected_before_mutation(self):
  for e in [FootballPlay('sack','H',8,'q'),FootballPlay('pass','H',3,'q','r',complete=True,interception=True),FootballPlay('rush','H',3,runner='other'),FootballPlay('pass','H',3,'q','r',touchdown=True)]:
   l=FootballLedger('NFL',['H','A'],self.owners)
   with self.assertRaises(ValueError):l.apply(e)
   self.assertEqual(l.events,0)
 def test_verified_absence_prevents_future_credit(self):
  l=FootballLedger('NFL',['H','A'],self.owners);l.apply(FootballPlay('rush','H',4,runner='b'));l.exclude('b')
  with self.assertRaises(ValueError):l.apply(FootballPlay('rush','H',4,runner='b'))
  self.assertEqual(l.team['H']['rushingYards'],4)
 def test_touchdown_try_and_fieldgoal_score_components(self):
  l=FootballLedger('NFL',['H','A'],self.owners);l.apply(FootballPlay('pass','H',5,'q','r',complete=True,touchdown=True));l.apply(FootballPlay('administrative','H',is_try=True,conversion_points=1));l.apply(FootballPlay('field_goal','H',made=True));self.assertEqual(l.team['H']['points'],10);l.verify()
class ClockAndOvertimeTests(unittest.TestCase):
 def test_regulation_quarters_conserve_time(self):
  for sport,length in [('NFL',900),('CFB',900),('NBA',720)]:
   c=RegulationClock(sport,2024)
   for _ in range(4):c.advance(length);c.next_period()
   c.verify_complete();self.assertEqual(c.elapsed,4*length)
 def test_unverified_runoff_and_period_skips_fail(self):
  c=RegulationClock('CFB',2024)
  with self.assertRaises(ValueError):c.advance(10,kind='runoff')
  with self.assertRaises(ValueError):c.next_period()
  with self.assertRaises(ValueError):c.advance(901)
 def test_two_minute_state_is_explicit_and_season_specific(self):
  c=RegulationClock('CFB',2024,period=2,remaining=125);c.advance(8);self.assertTrue(c.pending_warning);self.assertFalse(c.first_down_rule()['automaticFirstDownStop']);c.take_warning();self.assertTrue(c.first_down_rule()['automaticFirstDownStop']);c.next_period if False else None
  old=RegulationClock('CFB',2022,period=1,remaining=400);self.assertTrue(old.first_down_rule()['automaticFirstDownStop']);new=RegulationClock('CFB',2023,period=1,remaining=400);self.assertFalse(new.first_down_rule()['automaticFirstDownStop'])
 def test_runoff_elections_and_timeout_avoidance(self):
  self.assertEqual(runoff_seconds('NFL','injury',4,90,True),10);self.assertEqual(runoff_seconds('CFB','injury',4,90,True),0);self.assertEqual(runoff_seconds('CFB','foul',2,40,True),10);self.assertEqual(runoff_seconds('NFL','foul',4,40,True,timeout_used=True),0);self.assertEqual(runoff_seconds('NFL','foul',4,40,False),0)
 def test_half_distance_uses_actual_enforced_yards(self):
  field,enforced=dead_ball_enforcement(95,5);self.assertEqual(field,97.5);self.assertEqual(enforced,2.5);field,enforced=dead_ball_enforcement(5,5,True);self.assertEqual(field,2.5)
 def test_nfl_first_td_differs_in_2024_and_2025(self):
  a=FootballOvertime('NFL',2024,first=0);self.assertTrue(a.finish_possession(0,6,60));b=FootballOvertime('NFL',2025,first=0);self.assertFalse(b.finish_possession(0,7,60));self.assertFalse(b.finish_possession(1,7,60));self.assertTrue(b.finish_possession(0,3,30))
 def test_nfl_clock_expiration_and_postseason(self):
  a=FootballOvertime('NFL',2025);self.assertTrue(a.finish_possession(0,0,600));b=FootballOvertime('NFL',2024,postseason=True);self.assertFalse(b.finish_possession(0,7,60));self.assertTrue(b.finish_possession(1,0,60))
 def test_ncaa_eight_overtime_sequence(self):
  c=FootballOvertime('CFB',2024,first=0)
  for period,pair in enumerate([(7,7),(6,6),(0,0),(0,0),(2,2),(0,0),(0,0),(0,2)],1):
   self.assertEqual(c.period,period);self.assertEqual(c.shootout,period>=3);first=c.offense;c.finish_possession(first,pair[0]);c.finish_possession(1-first,pair[1])
  self.assertTrue(c.finished);self.assertEqual(c.period,8)
 def test_ncaa_shootout_is_untimed_and_not_normal_offense(self):
  c=FootballOvertime('CFB',2024,period=3)
  with self.assertRaises(ValueError):c.finish_possession(0,6)
  with self.assertRaises(ValueError):c.finish_possession(0,2,1)
  l=FootballLedger('CFB',['H','A'],{});l.apply(FootballPlay('administrative','H',is_try=True,conversion_points=2));l.verify();self.assertEqual(l.team['H']['offensivePlays'],0)
 def test_game_ending_touchdown_does_not_get_a_phantom_xp(self):
  self.assertFalse(try_required([6,0],0,overtime=FootballOvertime('NFL',2024)));self.assertTrue(try_required([6,0],0,overtime=FootballOvertime('NFL',2025)));self.assertFalse(try_required([6,3],0,overtime=FootballOvertime('CFB',2024,turns=1)));self.assertFalse(try_required([24,20],0,RegulationClock('NFL',2024,period=4,remaining=0)))
class BasketballTests(unittest.TestCase):
 def setUp(self):
  self.owners={**{str(i):'H' for i in range(1,7)},**{str(i):'A' for i in range(11,17)}};self.l=BasketballLedger(['H','A'],self.owners);self.l.set_lineup('H',[str(i) for i in range(1,6)]);self.l.set_lineup('A',[str(i) for i in range(11,16)])
 def test_shots_points_rebounds_and_joint_props(self):
  l=self.l;l.tick(720);l.shot('H','1',3,True,assist='2');l.shot('A','11',2,False,block='3');l.rebound('H','4');l.verify(720);self.assertEqual(l.players['1']['pointsReboundsAssists'],3);self.assertEqual(l.players['2']['assists'],1);self.assertEqual(l.players['4']['rebounds'],1)
 def test_only_the_final_missed_free_throw_is_reboundable(self):
  l=self.l;l.free_throw('H','1',False,False)
  with self.assertRaises(ValueError):l.rebound('A','11')
  l.free_throw('H','1',False,True);l.rebound('A','11')
  with self.assertRaises(ValueError):l.rebound('H','1')
 def test_technical_free_throw_has_no_live_rebound(self):
  self.l.free_throw('H','1',False,True,technical=True)
  with self.assertRaises(ValueError):self.l.rebound('A','11')
 def test_and_one_uses_shared_shooter_and_one_extra_point(self):
  self.l.and_one('H','1',2,True,assist='2');self.assertEqual(self.l.team['H']['points'],3);self.assertEqual(self.l.players['1']['fieldGoalAttempts'],1);self.assertEqual(self.l.players['1']['freeThrowAttempts'],1)
 def test_invalid_lineups_and_off_court_credit_rejected(self):
  with self.assertRaises(ValueError):self.l.set_lineup('H',['1','2','3','4','4'])
  with self.assertRaises(ValueError):self.l.shot('H','6',2,True)
  with self.assertRaises(ValueError):self.l.shot('H','1',2,True,assist='1')
 def test_substitution_and_injury_do_not_change_prior_minutes(self):
  l=self.l;l.tick(30);l.exclude('1');l.set_lineup('H',['6','2','3','4','5']);l.tick(30);l.verify(60);self.assertEqual(l.seconds['1'],30);self.assertEqual(l.seconds['6'],30)
 def test_corrected_same_clock_foul_precedes_replacement(self):
  rs=[{'id':1,'period_number':4,'clock_display_value':'1:04','sequence_number':701,'type_text':'Substitution','athlete_id_1':2,'athlete_id_2':1},{'id':2,'period_number':4,'clock_display_value':'1:04','sequence_number':711,'type_text':'Offensive Foul','athlete_id_1':1}];ordered=canonical_order(rs);self.assertEqual([r['id'] for r in ordered],[2,1])
class EvidenceAndParserTests(unittest.TestCase):
 def test_mode_a_cannot_publish_accuracy_or_win_probabilities(self):
  out=label({'brierScore':0,'homeWinProbability':.9},ctx('NFL'));self.assertNotIn('brierScore',out);self.assertNotIn('homeWinProbability',out);self.assertTrue(out['notAPregamePrediction'])
 def test_final_game_context_cannot_enter_forecast_gate(self):
  with self.assertRaisesRegex(ValueError,'Mode A/C'):qualify({'sport':'NFL'},{'id':'fixture:v23'},ctx('NFL'),{},None)
 def test_strict_gate_rejects_unverified_or_final_inputs(self):
  c=context(Mode.FORECAST,'NFL','fixture:v23',[SOURCE],cutoff='2024-01-01T00:00:00Z');model={'sport':'NFL','inputPolicy':'final_conditioned_mechanics','asOf':'2024-01-02T00:00:00Z'};model['sha256']=digest(model);q=qualify(model,{'id':'fixture:v23','cutoff':'2024-01-01T00:00:00Z'},c,{},None);self.assertFalse(q['strictQualified']);self.assertIn('model_inputs_not_point_in_time',q['reasons'])
 def test_overturned_original_does_not_nullify_current_touchdown(self):
  text='Play By Play\nHome drive starts at 01:40\n1-10 AWAY12  (01:40) Shotgun #1 A.Test pass complete to #2 B.Test for 12 yards TOUCHDOWN. (Original Play: pass incomplete PENALTY NO PLAY).\n';r=primary_actions(text,{'home':'H'},{'AWAY':'A'});self.assertEqual(len(r),1);self.assertFalse(r[0]['noPlay']);self.assertTrue(r[0]['complete']);self.assertEqual(r[0]['yards'],12)
 def test_duplicate_secondary_ids_need_one_primary_action_and_same_clock(self):
  p={'team':'cfb:espn:1','period':1,'down':1,'field':75,'kind':'pass','noPlay':False,'yards':0,'complete':False,'made':False,'sourceLine':'one independent play','action':'Q.Test pass incomplete'};r={'game_id':1,'pos_team_id':1,'period':1,'down':1,'start.yardsToEndzone':75,'clock.displayValue':'12:00','type.text':'Pass Incompletion','pass_attempt':True,'id':1,'text':'pass incomplete'};rs,proof=reconcile([r,r|{'id':2,'text':'Q.Test pass incomplete to R.Test'}],[p],SOURCE);self.assertEqual(len(proof['duplicateSecondaryEvents']),1);self.assertEqual(sum(bool(r.get('_duplicateOf')) for r in rs),1);self.assertNotIn('_duplicateOf',r)
 def test_primary_parenthesized_yards_are_preserved(self):
  text='Play By Play\nHome drive starts at 01:40\n1-10 AWAY30 #1 A.Test rush for 28 yards gain (19) to the AWAY02 PENALTY Home Holding 10 yards.\n';r=primary_actions(text,{'home':'H'},{'AWAY':'A'});self.assertEqual(r[0]['yards'],19);self.assertFalse(r[0]['noPlay'])
class GeneratedFootballTests(unittest.TestCase):
 def test_play_kernel_cache_does_not_alias_distances_or_score_signs(self):
  rows=fixture('NFL');teams=sorted({r['o'] for r in rows})[:2];rows=[r for r in rows if r['o'] in teams];k=PlayKernel('NFL',teams,rows,{})
  for field,distance,diff in [(50,1,1),(51,1,1),(50,2,1),(50,1,-1)]:k.select(np.random.default_rng(1),teams[0],3,field,600,diff,period=1,distance=distance)
  self.assertEqual(len(k.cache),4)
 def test_quarter_end_is_not_implicitly_half_end_for_kneels(self):
  rows=fixture('NFL');teams=sorted({r['o'] for r in rows})[:2];rows=[r for r in rows if r['o'] in teams]
  for r in rows[::10]:r['kind']='kneel'
  k=PlayKernel('NFL',teams,rows,{});rng=np.random.default_rng(2)
  for _ in range(20):self.assertNotEqual(k.select(rng,teams[0],1,50,100,7,period=1)['kind'],'kneel')
 def test_complete_joint_games_reconcile_both_leagues(self):
  for sport in ['NFL','CFB']:
   rows=fixture(sport);teams=sorted({r['o'] for r in rows})[:2];rows=[r for r in rows if r['o'] in teams]
   # The legacy synthetic fixture assigned completion and interception
   # independently. Make this software fixture legal; real contradictory
   # records are never repaired by this test convention.
   for r in rows:r['complete']=int(r['kind']=='pass' and r['complete'] and not r['int']);r['int']=int(r['kind']=='pass' and r['int'])
   owners={p:r['o'] for r in rows for p in [r.get('qb'),r.get('runner'),r.get('receiver')] if p};kernel=PlayKernel(sport,teams,rows,owners);a=football_games(kernel,ctx(sport),2024,2,23001,{'extra_point':[0,1],'two_point':[0,1]});b=football_games(kernel,ctx(sport),2024,2,23001,{'extra_point':[0,1],'two_point':[0,1]});self.assertEqual(a,b);self.assertTrue(a['mechanicalInvariantsPassed']);self.assertTrue(all(r['regulationSeconds']==3600 for r in a['results']))

class PhaseAndTransitionTests(unittest.TestCase):
 def test_four_partial_quarters_do_not_prove_clock_conservation(self):
  rows=[{'play_id':q,'qtr':q,'quarter_seconds_remaining':400} for q in range(1,5)];r=clock_audit(rows,'NFL');self.assertFalse(r['boundaryConservation']);self.assertEqual(r['observedAnchoredSeconds'],0)
 def law(self):return PhaseClockLaw([{'sport':'CFB','kind':'pass','seconds':3,**SOURCE}],'CFB')
 def test_incompletion_has_no_running_clock_burn(self):
  c=RegulationClock('CFB',2024);self.law().advance(np.random.default_rng(1),c,'pass',False,40);self.assertEqual(c.remaining,897);self.assertFalse(c.running)
 def test_zero_coarsened_charge_does_not_make_a_zero_duration_play(self):
  c=RegulationClock('CFB',2024);self.law().advance(np.random.default_rng(1),c,'rush',False,0);self.assertEqual(c.remaining,897)
 def test_running_phase_stops_at_two_minute_warning(self):
  c=RegulationClock('CFB',2024,period=4,remaining=130);self.law().advance(np.random.default_rng(1),c,'pass',True,40);self.assertEqual(c.remaining,120);self.assertTrue(c.warning_taken);self.assertFalse(c.running)
 def test_no_play_administration_only_burns_running_clock(self):
  c=RegulationClock('CFB',2024);law=self.law();law.advance(np.random.default_rng(1),c,'penalty',False,12);self.assertEqual(c.remaining,900);c.running=True;law.advance(np.random.default_rng(1),c,'penalty',False,12);self.assertEqual(c.remaining,888)
 def test_no_clock_source_means_no_timing_law(self):
  with self.assertRaises(ValueError):PhaseClockLaw([],'CFB')
 def test_restart_field_distinguishes_good_and_missed_kicks(self):
  class K:teams=['H','A'];sport='NFL';rows={'H':[{'kind':'punt','puntNet':40}]}
  rng=np.random.default_rng(1);self.assertEqual(restart_field(K(),rng,0,'field_goal_made',30,2024),70);self.assertEqual(restart_field(K(),rng,0,'field_goal_missed',30,2024),63);self.assertEqual(restart_field(K(),rng,0,'turnover',30,2024),70);self.assertEqual(restart_field(K(),rng,0,'punt',75,2024),65)
 def test_primary_spike_is_clock_anchored_without_a_fabricated_sequence(self):
  rows=[{'id':'a','period':2,'sequenceNumber':1,'clock.displayValue':'0:30'},{'id':'b','period':2,'sequenceNumber':2,'clock.displayValue':'0:08'},{'id':'primary','period':2,'clock.displayValue':'0:24','adapterOrderIsNotProviderSequence':True}];ordered=ordered_rows(rows,'CFB');self.assertEqual([r['id'] for r in ordered],['a','primary','b']);self.assertNotIn('sequenceNumber',rows[-1])

class GeneratedBasketballTests(unittest.TestCase):
 def game(self):
  players=[]
  for t,start in [('H',1),('A',11)]:
   for i in range(6):players.append({'athlete_id':start+i,'team_id':t,'minutes':40,'starter':i<5,'turnovers':2,'field_goals_attempted':10,'field_goals_made':5,'three_point_field_goals_attempted':4,'three_point_field_goals_made':2,'free_throws_attempted':4,'free_throws_made':3,'assists':3,'offensive_rebounds':1,'defensive_rebounds':4,'steals':1,'blocks':1,'fouls':2})
  teams={t:{'turnovers':12,'field_goals_attempted':60,'field_goals_made':30,'three_point_field_goals_attempted':24,'free_throws_attempted':24,'assists':18,'offensive_rebounds':6,'defensive_rebounds':24,'blocks':6,'steals':6} for t in ['H','A']}
  return {'teams':teams,'players':players,'freeThrowTrips':{'H':[2,3],'A':[2]},'stints':[120,180]}
 def test_complete_games_minutes_and_rebound_opportunities(self):
  r=basketball_games(self.game(),ctx('NBA'),2,23001,[4,8,12]);self.assertTrue(r['mechanicalInvariantsPassed'])
  for row in r['results']:self.assertEqual(row['seconds'],2880+300*row['overtimePeriods']);self.assertEqual(row['reboundableMisses'],row['creditedRebounds'])
 def test_sourced_injury_changes_rotation_not_past_credits(self):
  change={'playerId':'1','teamId':'H','status':'out','period':1,'remaining':720,**SOURCE};r=basketball_games(self.game(),ctx('NBA'),1,23001,[4,8,12],[change]);self.assertTrue(all(v==0 for v in r['results'][0]['players'].get('1',{}).values()));self.assertGreater(r['results'][0]['substitutions'],0)
 def test_complete_generated_overtime_extends_minutes_by_five_times_300(self):
  # Deliberate deterministic software fixture: equal even shot counts in
  # regulation, odd count in a 300-second OT. Never a historical forecast.
  game=self.game()
  for p in game['players']:
   p.update(field_goals_attempted=10,field_goals_made=10,three_point_field_goals_attempted=0,three_point_field_goals_made=0,free_throws_attempted=0,free_throws_made=0,turnovers=0,assists=0)
  for t in game['teams'].values():t.update(field_goals_attempted=60,field_goals_made=60,three_point_field_goals_attempted=0,free_throws_attempted=0,turnovers=0,assists=0)
  r=basketball_games(game,ctx('NBA'),1,23001,[12])['results'][0];self.assertEqual(r['overtimePeriods'],1);self.assertEqual(r['seconds'],3180);self.assertEqual(r['periodSeconds'],[720,720,720,720,300]);self.assertNotEqual(*r['scores'].values())
  for t in ['H','A']:self.assertAlmostEqual(sum(v['minutes'] for p,v in r['players'].items() if (int(p)<10)==(t=='H')),265)

class CompactStorageTests(unittest.TestCase):
 def test_aggregates_keep_zero_participation_and_float_minutes(self):
  rows=[{'scores':{'H':2,'A':1},'players':{'p':{'minutes':.5,'points':2}}},{'scores':{'H':0,'A':1},'players':{}}];r=compact({'researchContext':{'mode':Mode.MECHANICS},'results':rows});self.assertIsNone(r['teamWinFrequencies']);self.assertEqual(r['playerDistributions']['p']['minutes']['mean'],.25);self.assertEqual(sum(v['count'] for v in r['playerDistributions']['p']['points']['histogram']),2)
 def test_raw_mc_frequency_is_never_labeled_calibrated(self):
  rows=[{'scores':{'H':2,'A':1},'players':{}},{'scores':{'H':0,'A':1},'players':{}}];r=compact({'researchContext':{'mode':Mode.FORECAST},'results':rows});p=r['teamWinFrequencies']['H'];self.assertEqual(p['rawProbability'],.5);self.assertIsNone(p['calibratedProbability']);self.assertLess(p['monteCarloInterval95'][0],.5);self.assertGreater(p['monteCarloInterval95'][1],.5)

class LocalPrimaryRegressionTests(unittest.TestCase):
 def test_real_nba_headerless_pages_remain_part_of_the_report(self):
  from pathlib import Path
  import json,gzip
  from .fullgame_v23.evidence import nba_rows
  root=Path(__file__).resolve().parents[1];receipts=root/'artifacts/fullgame-v23/sources/receipts';found=None
  for p in [p for d in ['fullgame-v23','overnight-v21','overnight-v20','integration-v22'] for p in (root/'artifacts'/d/'sources/receipts').glob('*.json')]:
   r=json.loads(p.read_text())
   if 'Injury-Report_2024-11-06_05PM.pdf' in r.get('url','') and r.get('object'):found=r;break
  if not found:self.skipTest('Public primary PDF not in local private research cache; no network in tests')
  body=gzip.decompress((root/found['object']).read_bytes());rows,issued=nba_rows(body);self.assertGreater(len(rows),40);self.assertTrue(any(r.get('matchup')=='LAL@MEM' for r in rows));self.assertEqual(issued,'2024-11-06T22:30:00+00:00')
