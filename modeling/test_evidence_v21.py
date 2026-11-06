"""Synthetic guard tests are not evidence of historical forecasting accuracy."""
import unittest,json,copy,itertools
import numpy as np
from .evidence_v21.clock import conditional_intervals,CensoredClock,regulation_clock
from .evidence_v21.io import canonical_article
from .evidence_v21.tiers import timestamped_fact,classify
from .evidence_v21.opportunities import capped_budget,LineupMinutes
from .evidence_v21.basketball import game_exposures
class ClockTests(unittest.TestCase):
 def test_printed_team_codes_and_clock_totals_are_not_fuzzy_joined(self):
  from .evidence_v21.clock_data import official_team_codes,official_drive_rows,clock_accounting
  text='MINNESOTA\nMIN 1st MIN14 14:54 Kickoff MIN23 11:31 Punt 6 - 9 03:23\nMICHIGAN\nUoM 1st UoM21 11:31 Punt MIN00 06:28 TOUCHDOWN 9 - 79 05:03'
  aliases={'minnesota':'MINN','michigan':'MICH'};codes=official_team_codes(text,aliases);rows=official_drive_rows(text,aliases);self.assertEqual(codes,{'MIN':'MINN','UoM':'MICH'});self.assertEqual([r['team'] for r in rows],['MINN','MICH']);a=clock_accounting([],rows,codes);self.assertEqual(a['driveElapsedSeconds'],506);self.assertEqual(a['overlappingDriveIntervals'],[]);self.assertEqual(a['quarters'][0]['unassignedRegulationSeconds'],394)
 def test_mixed_case_printed_field_codes_reconcile(self):
  from .evidence_v21.clock_data import official_sequences
  text='Play By Play report\n1st Quarter\nMichigan drive starts at 11:31\n1-10 UoM21 Shotgun #1 rush right for 2 yards'
  r=official_sequences([text],{'michigan':'MICH'},{'UoM':'MICH'});self.assertEqual(r[0]['plays'],[{'down':1,'field':79,'kind':'rush'}])
 def test_unlabeled_duplicate_chart_cannot_inherit_team_or_quarter(self):
  from .evidence_v21.clock_data import official_drive_rows
  t='Drive Chart report\nMICHIGAN\nUoM 1st UoM21 11:31 Punt MIN00 06:28 TOUCHDOWN 9 - 79 05:03\nDrive Chart report\nUoM 1st UoM21 11:31 Punt MIN00 06:28 TOUCHDOWN 9 - 79 05:03\nUoM MIN25 04:00 Kickoff UoM20 02:00 Punt 3 - -5 02:00'
  r=official_drive_rows(t,{'michigan':'MICH'});self.assertEqual(len(r),1)
 def test_statcrew_drive_start_is_not_a_second_physical_play(self):
  from .evidence_v21.clock_data import official_sequences
  text='Play By Play\nStart of 1st quarter, clock 15:00.\nBall St. at 10:15\n1st and 10 at BSU25 Ball St. drive start at 10:15.\n1st and 10 at BSU25 Player pass incomplete short left'
  r=official_sequences([text],{'ballst':'BALL'},{'BSU':'BALL'});self.assertEqual(len(r[0]['plays']),1);self.assertEqual(r[0]['plays'][0]['field'],75)
 def test_ncaa_timeout_state_is_not_invented_from_a_coarse_clock(self):
  from .evidence_v21.rules import first_down_clock
  self.assertIsNone(first_down_clock('CFB',2024,2,119)['automaticFirstDownStop']);self.assertTrue(first_down_clock('CFB',2024,2,119,True)['automaticFirstDownStop']);self.assertFalse(first_down_clock('CFB',2024,2,121)['automaticFirstDownStop']);self.assertTrue(first_down_clock('CFB',2022,1,600)['automaticFirstDownStop']);self.assertFalse(first_down_clock('NFL',2024,4,60)['automaticFirstDownStop'])
 def test_conditional_law_matches_exhaustive_enumeration_and_conserves_time(self):
  a=np.zeros(91);b=a.copy();a[1:3]=[.2,.8];b[1:3]=[.3,.7];r=conditional_intervals([a,b],3,21,30);p=.2*.7/(.2*.7+.8*.3);self.assertAlmostEqual(r['masses'][0][1],p);self.assertAlmostEqual(sum(r['meanSeconds']),3);self.assertTrue(all(sum(x)==3 for x in r['jointDraws']));self.assertTrue(all(min(x)>0 for x in r['jointDraws']))
 def test_impossible_clock_never_becomes_zero_time(self):
  p=np.zeros(91);p[5]=1
  with self.assertRaises(ValueError):conditional_intervals([p,p],1)
 def test_quarter_boundaries_and_overtime_separation(self):
  self.assertEqual(regulation_clock(1,900),3600);self.assertEqual(regulation_clock(4,0),0)
  with self.assertRaises(ValueError):regulation_clock(5,900)
 def test_anchors_require_independent_verification(self):
  c=CensoredClock()
  with self.assertRaises(ValueError):c.reconstruct({'sequenceVerified':False,'anchorVerified':True})
 def test_administrative_zero_requires_explicit_evidence(self):
  with self.assertRaises(ValueError):CensoredClock().mass({'kind':'administrative'})
 def test_future_training_cannot_fit_clock(self):
  with self.assertRaises(ValueError):CensoredClock().fit([{'eventEnd':'2024-11-02T00:00:00Z'}],'2024-11-01T00:00:00Z')
class HistoricalBoxTests(unittest.TestCase):
 def fixture(self):
  original={'id':'cfb:espn:1','at':'2024-09-01T00:00:00Z','end':'2024-09-01T04:00:00Z','sport':'CFB','home':'cfb:espn:10','away':'cfb:espn:20','teams':{}};players=[];teams=[]
  for t in (10,20):
   original['teams']['cfb:espn:'+str(t)]={'players':{},'opponent':'cfb:espn:'+str(30-t),'totals':{'targets':1,'score':7,'dropbacks':2}}
   base={'game_id':1,'team_id':t}
   players.extend([{**base,'category':'passing','athlete_id':t,'athlete_name':'QB','completions/passingAttempts':'1/1','passingYards':'10'},{**base,'category':'passing','athlete_id':-1,'athlete_name':'TEAM','completions/passingAttempts':'0/1','passingYards':'0'},{**base,'category':'rushing','athlete_id':t,'athlete_name':'QB','rushingAttempts':'1','rushingYards':'3'},{**base,'category':'receiving','athlete_id':t+100,'athlete_name':'Receiver','receptions':'1','receivingYards':'10'}]);teams.append({**base,'completionAttempts':'1/2','netPassingYards':'10','rushingAttempts':'1','rushingYards':'3'})
  return original,players,teams
 def test_anonymous_team_credit_cannot_be_assigned_to_opposing_qb(self):
  from .evidence_v21.football_boxes import repaired_packet,completion_evidence
  g=repaired_packet(*self.fixture())
  for t in ['cfb:espn:10','cfb:espn:20']:
   self.assertEqual(g['teams'][t]['unassignedTeamCredits']['passingAttempts'],1);self.assertEqual(g['teams'][t]['players'][t]['stats']['passingAttempts'],1);self.assertEqual(g['teams'][t]['totals']['passingAttempts'],2)
  e=completion_evidence([g],'2024-09-02T00:00:00Z');self.assertEqual(e['teamCompletionCounts']['cfb:espn:10'],[1,2])
 def test_inconsistent_official_box_is_not_forced_to_reconcile(self):
  from .evidence_v21.football_boxes import repaired_packet
  a,b,c=self.fixture();c[0]['rushingAttempts']='2'
  with self.assertRaises(ValueError):repaired_packet(a,b,c)
 def test_current_final_cannot_become_pregame_evidence(self):
  from .evidence_v21.football_boxes import repaired_packet,earlier_packets
  g=repaired_packet(*self.fixture());self.assertEqual(earlier_packets([g],g['at']),[]);self.assertEqual(earlier_packets([g],'2024-09-01T10:00:00Z'),[])
class SourceTests(unittest.TestCase):
 def test_protected_confirmation_outcomes_cannot_train_a_candidate(self):
  from .evidence_v21.protection import assert_unexposed
  with self.assertRaises(ValueError):assert_unexposed({'old','locked-confirmation'},{'sealed','locked-confirmation'})
  assert_unexposed({'old'},{'sealed','locked-confirmation'})
 def test_explicit_league_statuses_preserve_uncertainty_and_injury_commas(self):
  from .evidence_v21.availability import nfl_article_statuses
  r=nfl_article_statuses({'articleBody':'49ERS\nOUT: WR Player One (knee, ankle), LB Player Two (hip)\nQUESTIONABLE: RB Player Three (illness)\nNo designation: Player Four'})
  self.assertEqual(len(r),3);self.assertEqual(r[0]['teamId'],'SF');self.assertEqual(r[0]['injury'],'knee, ankle');self.assertEqual(r[2]['status'],'questionable');self.assertNotIn('healthy',str(r))
 def test_missing_position_and_comma_stay_explicit_without_fuzzy_names(self):
  from .evidence_v21.availability import nfl_article_statuses
  r=nfl_article_statuses({'articleBody':'BILLS\nOUT: Josh Palmer (shoulder), RB Runner One (knee) LB Defender Two (calf)'})
  self.assertEqual(len(r),3);self.assertIsNone(r[0]['position']);self.assertEqual(r[0]['playerName'],'Josh Palmer');self.assertEqual(r[2]['playerName'],'Defender Two')
 def test_wordpress_article_can_prove_its_own_canonical_identity(self):
  a={'@type':'NewsArticle','@id':'https://team.example/report/#article','mainEntityOfPage':{'@id':'https://team.example/report/'},'datePublished':'2024-01-01T00:00:00Z'};body=('<script type="application/ld+json">'+json.dumps({'@graph':[a]})+'</script>').encode();self.assertEqual(canonical_article(body,'https://team.example/report/'),a)
 def test_same_path_on_unrelated_host_cannot_supply_publication(self):
  a={'@type':'NewsArticle','url':'https://unrelated.example/report'};body=('<script type="application/ld+json">'+json.dumps(a)+'</script>').encode()
  with self.assertRaises(ValueError):canonical_article(body,'https://team.example/report')
 def test_related_article_dates_do_not_poison_canonical_report(self):
  a={'@type':'NewsArticle','url':'https://team.example/news/report','datePublished':'2024-09-20T00:00:00Z'};b={'@type':'NewsArticle','url':'https://team.example/news/other','datePublished':'2026-01-01T00:00:00Z'};body=('<script type="application/ld+json">'+json.dumps([a,b])+'</script>').encode();self.assertEqual(canonical_article(body,a['url']),a)
 def test_ambiguous_canonical_articles_withheld(self):
  a={'@type':'NewsArticle','url':'https://team.example/news/report'};body=('<script type="application/ld+json">'+json.dumps([a,a])+'</script>').encode()
  with self.assertRaises(ValueError):canonical_article(body,a['url'])
 def test_modified_after_kickoff_cannot_supply_pregame_fact(self):
  with self.assertRaises(ValueError):timestamped_fact('https://team.example/report','sha','2024-01-01T00:00:00Z','2026-01-01T00:00:00Z','2024-01-02T00:00:00Z',modified='2024-01-03T00:00:00Z')
 def test_genuine_publication_is_distinct_from_independent_capture(self):
  r=timestamped_fact('https://team.example/report','sha','2024-01-01T00:00:00Z','2026-01-01T00:00:00Z','2024-01-02T00:00:00Z');self.assertEqual(r['timestampClass'],'publisher_dated_pregame');self.assertIsNone(r['independentCaptureAt']);self.assertFalse(r['unknownIsHealthy'])
 def test_unknown_injury_remains_conditional_and_cannot_start_full_game(self):
  r=classify('CFB','game','2024-01-01T00:00:00Z',{},consistency={'clock':True});self.assertEqual(r['tier'],'conditional_diagnostic');self.assertFalse(r['fullGameSimulationAllowed']);self.assertFalse(r['missingMeansHealthy'])
 def test_failed_consistency_blocks_even_conditional_diagnostics(self):
  r=classify('NBA','game','2024-01-01T00:00:00Z',{},consistency={'roster':False});self.assertEqual(r['tier'],'blocked');self.assertFalse(r['conditionalComponentDiagnosticsAllowed'])
class MinutesTests(unittest.TestCase):
 def test_archived_state_projection_is_restored_without_mutating_forecast(self):
  from .evidence_v21.forecast_schema import nested_predictions
  r={'predictions':{'raw_hurdle':20.},'lineup_state_minutes':21.};q=nested_predictions(r);self.assertEqual(q['predictions']['lineup_state_minutes'],21.);self.assertNotIn('lineup_state_minutes',r['predictions']);self.assertEqual(nested_predictions(q),q)
 def test_proportional_minutes_preserve_zero_and_relative_workload(self):
  from .evidence_v21.rates import proportional_budget
  r=proportional_budget([40,35,30,25,20,15,10,5,0],240,48);self.assertAlmostEqual(r.sum(),240);self.assertEqual(r[-1],0);self.assertTrue(np.all(r<=48));self.assertAlmostEqual(r[-2]/r[-3],.5)
 def test_opportunity_attribution_reconciles_and_does_not_claim_causation(self):
  from .evidence_v21.rates import factor_attribution
  d=factor_attribution([30,.8,8],[40,.9,6]);self.assertAlmostEqual(sum(d),30*.8*8-40*.9*6);self.assertEqual(factor_attribution([3,4],[3,4]),[0,0])
 def test_proportional_minutes_cannot_invent_a_fifth_participant(self):
  from .evidence_v21.rates import proportional_budget
  with self.assertRaises(ValueError):proportional_budget([40,40,40,40,0],240,48)
 def test_lineup_published_after_prediction_cutoff_is_rejected_even_before_tip(self):
  m=LineupMinutes().fit(self.fixture(),'2024-11-01T00:00:00Z');rows=[{**r,'gameId':'new','at':'2024-11-02T00:00:00Z'} for r in self.fixture()[:8]];f={'kind':'confirmed_starting_lineup','source':'https://team.example','sourceVersion':'sha','eventId':'new','publishedAt':'2024-11-01T23:45:00Z','players':['0','1','2','3','4']}
  with self.assertRaises(ValueError):m.predict_team(rows,lineup_fact=f)
 def test_bounded_minutes_reconcile_without_negative_workloads(self):
  r=capped_budget([70,50,40,30,20,10,0,0],240,48);self.assertAlmostEqual(r.sum(),240);self.assertTrue(np.all((r>=0)&(r<=48)))
 def test_inadequate_roster_cannot_be_filled_with_fictitious_players(self):
  with self.assertRaises(ValueError):capped_budget([40]*4,240,48)
 def fixture(self):
  return [{'gameId':'old'+str(i//8),'at':'2024-10-01T00:00:00Z','stat':'minutes','player':str(i%8),'team':'t','x':[i%8/8,1],'featureNames':['prior_role','constant'],'y':30 if i%8<5 else 10,'actualStarter':i%8<5} for i in range(240)]
 def test_current_actual_starters_are_not_inputs(self):
  m=LineupMinutes().fit(self.fixture(),'2024-11-01T00:00:00Z');rows=[{**r,'gameId':'new','at':'2024-11-02T00:00:00Z'} for r in self.fixture()[:8]];a=m.predict_team(rows);b=m.predict_team([{**r,'actualStarter':not r['actualStarter'],'y':99} for r in rows]);np.testing.assert_array_equal(a,b);self.assertAlmostEqual(a.sum(),240)
 def test_postgame_lineup_cannot_be_supplied_as_pregame_fact(self):
  m=LineupMinutes().fit(self.fixture(),'2024-11-01T00:00:00Z');rows=[{**r,'gameId':'new','at':'2024-11-02T00:00:00Z'} for r in self.fixture()[:8]];f={'kind':'confirmed_starting_lineup','source':'https://team.example','sourceVersion':'sha','eventId':'new','publishedAt':'2024-11-03T00:00:00Z','players':['0','1','2','3','4']}
  with self.assertRaises(ValueError):m.predict_team(rows,lineup_fact=f)
class LineupTests(unittest.TestCase):
 def fixture(self):
  players=[{'athlete_id':i,'team_id':'a' if i<10 else 'b','minutes':10,'starter':i in [1,2,3,4,5,11,12,13,14,15],'offensive_rebounds':int(i==6),'defensive_rebounds':0} for i in [1,2,3,4,5,6,11,12,13,14,15]];g={'id':'synthetic','teams':{'a':{},'b':{}},'players':players};rs=[]
  def event(period,clock,seq,text,a=None,b=None,kind='Jump Shot'):return {'id':str(seq),'period_number':period,'clock_display_value':clock,'sequence_number':seq,'text':text,'athlete_id_1':a,'athlete_id_2':b,'type_text':kind}
  rs=[event(1,'11:00',20,'Six enters the game for Five',6,5,'Substitution'),event(1,'10:00',10,'Six offensive rebound',6,None,'Offensive Rebound')]+[event(q,'0:00',q*100,'End period',kind='End Period') for q in range(1,5)];return g,rs
 def test_clock_order_handles_late_corrected_sequence_ids(self):
  g,rs=self.fixture();r=game_exposures(g,rs);self.assertTrue(r['complete']);self.assertEqual(r['players']['6']['exposure']['offensive_rebounds'],1);self.assertNotIn('offensive_rebounds',r['players']['5']['exposure']);self.assertIsNone(r['players']['1']['identifiedMinutes'])
 def test_missing_substitution_is_not_invented(self):
  g,rs=self.fixture();rs=[r for r in rs if r['type_text']!='Substitution']
  with self.assertRaises(ValueError):game_exposures(g,rs)
 def test_rebound_mismatch_fails_closed(self):
  g,rs=self.fixture();g['players'][0]['defensive_rebounds']=1
  with self.assertRaises(ValueError):game_exposures(g,rs)
if __name__=='__main__':unittest.main()
